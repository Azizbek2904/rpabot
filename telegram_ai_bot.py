"""
🤖 AI Mebel Sales Bot — FULL ODOO ERP INTEGRATION
Telegram ID orqali mijozni tanish | Hammasi Odoo ERP da
AI erkin suhbat | Avtomatik product yaratish
"""
import os, io, logging, time
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton as Btn, InlineKeyboardMarkup as KB
from telegram.ext import (Application, CommandHandler as Cmd, MessageHandler as Msg,
                          CallbackQueryHandler as Cbq, ConversationHandler as Conv, filters)
from odoo_auto_connector import OdooAutoConnector
from ai_engine import AIEngine
from ocr_processor import OCRProcessor
from workflow_logger import WorkflowLogger

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN = os.getenv("ADMIN_CHAT_ID")
MIN_M = float(os.getenv("MIN_PROFIT_MARGIN", "10"))

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

CHAT, NAME, PHONE, EMAIL, ADDR, NEW_PRICE, QTY, CART, PAY, DELIV = range(10)

# Faqat MEBEL nomlari (zaxira aniqlash uchun — "kerak/olaman" kabi niyat so'zlari emas)
FURNITURE_WORDS = [
    "stol", "stul", "divan", "shkaf", "krovat", "karavot", "kreslo", "polka",
    "tumba", "mebel", "yotoq", "komod", "oshxona", "gardirob", "tryumo",
    "bolalar mebel", "ofis stol", "ko'zgu", "kozgu", "matras", "matrac",
    "sandiq", "kursi", "stellaj", "vitrina", "tryumo",
]

odoo = OdooAutoConnector()
ai = AIEngine(min_margin=MIN_M)
ocr = OCRProcessor()
wl = WorkflowLogger()
db = {}
_pc = {"d": "", "t": 0}


def S(cid):
    if cid not in db:
        db[cid] = {"cust": {}, "items": [], "pid": None, "so": None, "inv": None,
                   "addr": "", "dcost": 0, "hist": "", "cur": None, "identified": False}
    return db[cid]


async def adm(ctx, t):
    if ADMIN:
        try: await ctx.bot.send_message(int(ADMIN), t, parse_mode="Markdown")
        except: pass


def prods():
    now = time.time()
    if now - _pc["t"] < 60 and _pc["d"]: return _pc["d"]
    try:
        odoo.connect(); ps = odoo.get_all_products(20)
        r = "\n".join([f"- {p['name']}: {p['price']:,.0f}" for p in ps]) if ps else ""
        _pc["d"] = r; _pc["t"] = now; return r
    except: return _pc["d"]


async def send(src, text, **kw):
    try:
        if hasattr(src, "edit_message_text"): await src.edit_message_text(text, **kw)
        elif hasattr(src, "message") and src.message: await src.message.reply_text(text, **kw)
    except: pass


def deliv_kb():
    """Yetkazib berishni tasdiqlash tugmalari."""
    return KB([[Btn("✅ Qabul qildim", callback_data="DOK")],
               [Btn("❌ Hali yetmadi", callback_data="DNO")]])


async def identify_customer(cid, context=None):
    """Telegram ID orqali Odoo ERP dan mijozni topish."""
    s = S(cid)
    if s["identified"] and s.get("pid"):
        return True

    odoo.connect()
    partner = odoo.find_partner_by_telegram(cid)
    if partner:
        s["pid"] = partner["id"]
        s["cust"] = {
            "name": partner.get("name", ""),
            "phone": partner.get("phone", ""),
            "email": partner.get("email", ""),
        }
        s["addr"] = partner.get("street", "") or ""
        s["identified"] = True
        log.info(f"🔍 Identified: {partner.get('name')} (TG:{cid}) → partner #{partner['id']}")
        return True
    return False


# ════════════ COMMANDS ════════════
async def cmd_start(u: Update, ctx):
    cid = u.effective_chat.id; s = S(cid)
    s["items"] = []; s["cur"] = None

    # Telegram ID orqali tanish
    found = await identify_customer(cid)

    if found:
        name = s["cust"].get("name", "")
        orders = odoo.get_partner_orders(s["pid"], 3)
        orders_text = ""
        if orders:
            orders_text = "\n\n📋 *Oxirgi buyurtmalaringiz:*\n"
            for o in orders:
                orders_text += f"  • {o.get('name','')} — {o.get('amount_total',0):,.0f} — {o.get('state','')}\n"

        await u.message.reply_text(
            f"👋 *Assalomu alaykum, {name}!*\n\n"
            f"Men — *{ai.company}* mebel botiman.\n"
            f"Sizni tanidim! 🎉{orders_text}\n\n"
            f"🪑 Qanday mebel kerak? Yozing!\n"
            f"🛒 /catalog — Mebellar\n❓ /help — Yordam",
            parse_mode="Markdown")
    else:
        # Yangi mijoz — ism SO'RAMAYMIZ. Faqat zakaz berganda so'raymiz.
        await u.message.reply_text(
            f"🪑 *Assalomu alaykum!*\n\n"
            f"Men — *{ai.company}* mebel botiman.\n"
            f"📦 Bizda yo'q bo'lsa — *topib beramiz!*\n\n"
            f"🪑 Qanday mebel kerak? Yozing!\n"
            f"🛒 /catalog — Mebellar\n❓ /help — Yordam",
            parse_mode="Markdown")

    return CHAT


async def cmd_help(u: Update, ctx):
    await u.message.reply_text(
        "🪑 Mebel nomini yozing — topamiz!\n🛒 /catalog — barcha mebellar\n"
        "📋 /myorders — buyurtmalarim\n❌ /cancel — bekor\n\n"
        "💡 *Bizda yo'q bo'lsa ham buyurtma bering — topib beramiz!*",
        parse_mode="Markdown")
    return CHAT


async def cmd_cancel(u: Update, ctx):
    s = S(u.effective_chat.id); s["items"] = []; s["cur"] = None
    await u.message.reply_text("❌ Bekor. Yana yozing! 🪑"); return CHAT


async def cmd_catalog(u: Update, ctx):
    cid = u.effective_chat.id
    await identify_customer(cid)
    odoo.connect(); ps = odoo.get_all_products(20)
    if not ps:
        await u.message.reply_text("📦 Katalog hozircha bo'sh.\n🔍 Lekin *istalgan mebelni yozing* — topib beramiz!", parse_mode="Markdown")
        return CHAT
    text = "🪑 *Mebellar:*\n\n"
    kb = []
    for p in ps:
        text += f"• *{p['name']}* — {p['price']:,.0f} so'm\n"
        kb.append([Btn(f"🛒 {p['name']} — {p['price']:,.0f}", callback_data=f"B{p['id']}_{p['price']}")])
    kb.append([Btn("🔍 Boshqa mebel kerak", callback_data="BSEARCH")])
    await u.message.reply_text(text + "\n👆 Tanlang yoki boshqa mebel nomini yozing!", reply_markup=KB(kb), parse_mode="Markdown")
    return CHAT


async def cmd_orders(u: Update, ctx):
    cid = u.effective_chat.id; s = S(cid)
    await identify_customer(cid)

    if s.get("pid"):
        orders = odoo.get_partner_orders(s["pid"], 10)
        if orders:
            text = "📋 *Buyurtmalaringiz (Odoo ERP):*\n\n"
            for o in orders:
                state_emoji = {"sale": "✅", "done": "🎉", "cancel": "❌", "draft": "📝"}.get(o.get("state", ""), "📦")
                text += f"  {state_emoji} *{o.get('name', '')}* — {o.get('amount_total', 0):,.0f} so'm — {o.get('state', '')}\n"
            await u.message.reply_text(text, parse_mode="Markdown")
            return
    # Savatdagi
    if s.get("items"):
        total = sum(i["sub"] for i in s["items"])
        lines = "\n".join([f"  {n+1}. {i['name']} × {i['qty']} = {i['sub']:,.0f}" for n, i in enumerate(s["items"])])
        await u.message.reply_text(f"📋 *Hozirgi savat:*\n{lines}\n💰 {total:,.0f}", parse_mode="Markdown")
    else:
        await u.message.reply_text("📋 Buyurtma yo'q. /catalog yoki mebel nomini yozing!")


# ════════════ AI CHAT — ERKIN SUHBAT ════════════
async def on_chat(u: Update, ctx):
    cid = u.effective_chat.id; msg = u.message.text.strip(); s = S(cid)
    await identify_customer(cid)

    # Context
    context = ""
    if s["items"]:
        context = "Savat: " + ", ".join([f"{i['name']}x{i['qty']}" for i in s["items"]])
    if s["cust"].get("name"):
        context += f" Mijoz: {s['cust']['name']}"

    s["hist"] += f"\nM:{msg}"
    if len(s["hist"]) > 2000:
        s["hist"] = "\n".join(s["hist"].split("\n")[-15:])

    # AI javob — erkin suhbat
    raw_reply = ai.chat(msg, prods(), s["cust"].get("name", ""), context, s["hist"])

    # AI javobidan MAHSULOT markerini ajratib olamiz
    product_name, reply = ai.extract_product(raw_reply)
    s["hist"] += f"\nB:{reply[:150]}"

    # Buyurtma tayyor
    if "BUYURTMA_TAYYOR" in reply:
        reply = reply.replace("BUYURTMA_TAYYOR", "").strip()
        if reply:
            await u.message.reply_text(reply)
        if not s.get("pid"):
            await u.message.reply_text("👤 Buyurtma uchun ismingizni yozing:")
            return NAME
        return await go_addr(u, ctx, cid)

    # AI marker bermagan bo'lsa — kalit so'z bo'yicha zaxira aniqlash (FAQAT mebel nomlari)
    if not product_name and any(w in msg.lower() for w in FURNITURE_WORDS):
        product_name = msg.strip()

    # Mebel so'ralgan bo'lsa → avval katalogdan qidiramiz
    if product_name:
        odoo.connect()
        found = odoo.search_products(product_name)
        if found:
            kb = [[Btn(f"🛒 {p['name']} — {p['price']:,.0f}", callback_data=f"B{p['id']}_{p['price']}")]
                  for p in found[:5]]
            await u.message.reply_text((reply + "\n\n🔍 Katalogdan topildi:").strip(), reply_markup=KB(kb))
            return CHAT

        # Katalogda yo'q → TOPIB BERAMIZ: narx baholash + Odoo ERP da yaratish
        price = ai.estimate_furniture_price(product_name)
        pid = odoo.find_or_create_product(product_name.strip().title(), price)
        if pid:
            s["cur"] = {"name": product_name.strip().title(), "id": pid, "price": price}
            kb = [
                [Btn(f"✅ {price:,.0f} so'mga olaman", callback_data=f"B{pid}_{price}")],
                [Btn("💰 Boshqa narx", callback_data="BPRICE")],
                [Btn("❌ Kerak emas", callback_data="BCANCEL")],
            ]
            await u.message.reply_text(
                f"🔍 *{product_name.strip().title()}*\n\n"
                f"📦 Bizda hozir yo'q, lekin *topib beramiz!* Odoo ERP ga qo'shildi.\n"
                f"💰 Taxminiy narx: *{price:,.0f} so'm*\n\nOlasizmi?",
                reply_markup=KB(kb), parse_mode="Markdown")
            return CHAT

    # Mebel emas / oddiy suhbat → AI javobi (kerak bo'lsa muloyim rad etadi)
    await u.message.reply_text(reply or "😊 Qanday mebel kerak? Yozing yoki /catalog bosing!")
    return CHAT


# ════════════ PRODUCT PICK ════════════
async def on_pick(u: Update, ctx):
    q = u.callback_query; await q.answer()
    cid = q.message.chat_id; s = S(cid)

    if q.data == "BSEARCH":
        await q.edit_message_text("🔍 Qanday mebel kerak? Nomini yozing:"); return CHAT
    if q.data == "BPRICE":
        await q.edit_message_text("💰 Narxingizni yozing (so'mda):"); return NEW_PRICE
    if q.data == "BCANCEL":
        s["cur"] = None; await q.edit_message_text("❌ OK. Yana yozing! 🪑"); return CHAT

    if q.data.startswith("B"):
        parts = q.data[1:].split("_"); pid, price = int(parts[0]), float(parts[1])
        info = odoo.get_product_info(pid); name = info["name"] if info else f"#{pid}"
        s["cur"] = {"name": name, "id": pid, "price": price}
        await q.edit_message_text(f"🪑 *{name}* — {price:,.0f} so'm\nNechta kerak?", parse_mode="Markdown")
        return QTY
    return CHAT


# ════════════ NEW PRICE ════════════
async def on_newprice(u: Update, ctx):
    cid = u.effective_chat.id; s = S(cid)
    try: price = float(u.message.text.strip().replace(",", "").replace(" ", "")); assert price > 0
    except: await u.message.reply_text("⚠️ Musbat raqam yozing:"); return NEW_PRICE
    cur = s.get("cur")
    if cur:
        cur["price"] = price
        if cur.get("id"):
            try: odoo._r("product.product", "write", [[cur["id"]], {"list_price": price}])
            except: pass
        await u.message.reply_text(f"✅ *{cur['name']}* — {price:,.0f} so'm\nNechta kerak?", parse_mode="Markdown")
        return QTY
    await u.message.reply_text("❌ Avval mebel tanlang. /catalog"); return CHAT


# ════════════ QUANTITY ════════════
async def on_qty(u: Update, ctx):
    cid = u.effective_chat.id; s = S(cid)
    try: qty = int(u.message.text.strip()); assert qty > 0
    except: await u.message.reply_text("⚠️ Musbat son yozing:"); return QTY
    cur = s.get("cur")
    if not cur: await u.message.reply_text("❌ /catalog bosing!"); return CHAT

    s["items"].append({"name": cur["name"], "pid": cur.get("id"), "qty": qty, "price": cur["price"], "sub": qty * cur["price"]})
    s["cur"] = None
    total = sum(i["sub"] for i in s["items"])
    lines = "\n".join([f"  {n+1}. {i['name']} × {i['qty']} = {i['sub']:,.0f}" for n, i in enumerate(s["items"])])
    kb = [[Btn("➕ Yana mebel", callback_data="MA")], [Btn("✅ Buyurtma", callback_data="MD")], [Btn("❌ Bekor", callback_data="MC")]]
    await u.message.reply_text(f"✅ Qo'shildi!\n\n📋 *Buyurtma:*\n{lines}\n💰 *Jami:* {total:,.0f}", reply_markup=KB(kb), parse_mode="Markdown")
    return CART


# ════════════ CART ════════════
async def on_cart(u: Update, ctx):
    q = u.callback_query; await q.answer(); cid = q.message.chat_id; s = S(cid)
    if q.data == "MA": await q.edit_message_text("🪑 Yozing yoki /catalog:"); return CHAT
    if q.data == "MC": s["items"] = []; await q.edit_message_text("❌ Bekor."); return CHAT
    if q.data == "MD":
        if not s.get("pid"):
            await q.edit_message_text("👤 Ismingizni yozing:"); return NAME
        return await go_addr(q, ctx, cid)
    return CHAT


# ════════════ CUSTOMER (faqat yangilar uchun) ════════════
async def on_name(u: Update, ctx):
    cid = u.effective_chat.id; s = S(cid)
    s["cust"]["name"] = u.message.text.strip()
    # Odoo ERP da yaratish — Telegram ID bilan
    odoo.connect()
    s["pid"] = odoo.find_or_create_partner(s["cust"]["name"], telegram_id=cid)
    s["identified"] = True
    log.info(f"New customer: {s['cust']['name']} TG:{cid} → partner #{s['pid']}")
    await u.message.reply_text(f"✅ *{s['cust']['name']}*, Odoo ERP da yaratildi! 🎉\n📱 Telefon raqamingiz:", parse_mode="Markdown")
    return PHONE

async def on_phone(u: Update, ctx):
    cid = u.effective_chat.id; s = S(cid)
    s["cust"]["phone"] = u.message.text.strip()
    if s.get("pid"):
        try: odoo._r("res.partner", "write", [[s["pid"]], {"phone": s["cust"]["phone"]}])
        except: pass
    # Email SO'RAMAYMIZ — to'g'ridan-to'g'ri manzil/buyurtmaga
    if s.get("items"):
        return await go_addr(u, ctx, cid)
    await u.message.reply_text("✅ Tayyor! Endi mebel tanlang:\n🛒 /catalog yoki nom yozing! 🪑")
    return CHAT


# ════════════ ADDRESS ════════════
async def go_addr(src, ctx, cid):
    s = S(cid)
    if not s["items"]:
        await send(src, "🪑 Avval mebel tanlang! /catalog"); return CHAT
    # Agar manzil bor bo'lsa (Odoo dan)
    if s.get("addr"):
        await send(src, f"📍 Manzil: *{s['addr']}*\nTo'g'rimi? Yangi manzil yozing yoki *ha* bosing:", parse_mode="Markdown")
    else:
        await send(src, "📍 *Yetkazish manzilingiz?*\n(Shahar, tuman, ko'cha)", parse_mode="Markdown")
    return ADDR

async def on_addr(u: Update, ctx):
    cid = u.effective_chat.id; s = S(cid); msg = u.message.text.strip()
    if msg.lower() in ["ha", "yes", "ok", "to'g'ri"] and s.get("addr"):
        pass  # Mavjud manzilni ishlatamiz
    else:
        s["addr"] = msg
        # Odoo ERP da manzilni saqlash
        if s.get("pid"):
            odoo.update_partner_address(s["pid"], msg)

    dc, reg = ai.delivery_cost(s["addr"]); s["dcost"] = dc
    total = sum(i["sub"] for i in s["items"]); grand = total + dc
    lines = "\n".join([f"  🪑 {i['name']} × {i['qty']} = {i['sub']:,.0f}" for i in s["items"]])
    text = f"📋 *Buyurtma:*\n\n{lines}\n\n💰 Mebellar: {total:,.0f}\n🚚 Yetkazish ({reg}): {dc:,.0f}\n\n💵 *TO'LOV: {grand:,.0f} so'm*\n_(Soliq qo'shilishi mumkin)_"
    kb = [[Btn("✅ TASDIQLASH", callback_data="OY")], [Btn("❌ BEKOR", callback_data="ON")]]
    await u.message.reply_text(text + "\n\nTasdiqlaysizmi?", reply_markup=KB(kb), parse_mode="Markdown")
    return CART


# ════════════ ORDER → ODOO ERP ════════════
async def on_order(u: Update, ctx):
    q = u.callback_query; await q.answer(); cid = q.message.chat_id; s = S(cid)
    if q.data == "ON": s["items"] = []; await q.edit_message_text("❌ Bekor."); return CHAT
    if q.data == "OY":
        await q.edit_message_text("⏳ Odoo ERP da buyurtma yaratilmoqda...")
        odoo.connect()
        if not s.get("pid"):
            s["pid"] = odoo.find_or_create_partner(s["cust"].get("name", "Telegram User"), telegram_id=cid)

        lines = [{"product_name": i["name"], "quantity": i["qty"], "price": i["price"]} for i in s["items"]]
        if s["dcost"] > 0:
            lines.append({"product_name": "Mebel yetkazish", "quantity": 1, "price": s["dcost"]})

        qid, qi = odoo.create_quotation(s["pid"], lines)
        if not qid: await ctx.bot.send_message(cid, f"⚠️ {qi}"); return CHAT

        s["so"] = qid
        res = odoo.full_confirm_order(qid)
        s["inv"] = res.get("inv_id")

        # Real summa (tax bilan) — Odoo ERP dan
        pay = res.get("total", 0)
        if s.get("inv"):
            try:
                iv = odoo._r("account.move", "read", [[s["inv"]]], {"fields": ["amount_residual"]})
                if iv: pay = iv[0].get("amount_residual", pay)
            except: pass

        bank = os.getenv("BANK_NAME", "Kapitalbank"); acc = os.getenv("BANK_ACCOUNT", "2020 0000 1234 5678")
        await ctx.bot.send_message(cid,
            f"🎉 *Buyurtma Odoo ERP da tasdiqlandi!*\n\n"
            f"📋 *{res.get('so_name', '')}*\n📄 {res.get('inv_name', '')}\n📍 {s['addr']}\n\n"
            f"💵 *To'lov: {pay:,.0f} so'm*\n\n🏦 {bank}\n💳 {acc}\n📝 {res.get('so_name', '')}\n\n📸 Kvitansiya yuboring!",
            parse_mode="Markdown")

        receipt = odoo.generate_receipt_text(s["inv"]) if s.get("inv") else None
        if receipt: await ctx.bot.send_message(cid, f"```\n{receipt}\n```", parse_mode="Markdown")
        wl.log("order", cid, res.get("so_name", ""))
        await adm(ctx, f"🪑 {res.get('so_name', '')} | {s['cust'].get('name', '')}")
        return PAY
    return CHAT


# ════════════ PAYMENT ════════════
async def on_pay(u: Update, ctx):
    cid = u.effective_chat.id; s = S(cid)
    photo = None
    if u.message.photo: photo = u.message.photo[-1]
    elif u.message.document: photo = u.message.document
    if not photo:
        r = ai.chat(u.message.text, customer=s["cust"].get("name", ""), context="To'lov kutilmoqda.")
        await u.message.reply_text(r + "\n\n📸 Kvitansiya yuboring!"); return PAY

    await u.message.reply_text("⏳ Tekshirmoqda... 🔍")
    try:
        f = await ctx.bot.get_file(photo.file_id); fb = await f.download_as_bytearray(); raw = bytes(fb)
        is_pdf = raw[:5] == b"%PDF-" or (getattr(photo, "file_name", "") or "").lower().endswith(".pdf")
        rec = (ocr.process_invoice_pdf(raw) or {"amount": 0, "raw_text": ""}) if is_pdf else ocr.process_receipt(raw)

        odoo.connect(); exp = 0
        if s.get("inv"):
            try:
                iv = odoo._r("account.move", "read", [[s["inv"]]], {"fields": ["amount_residual"]})
                if iv: exp = iv[0].get("amount_residual", 0)
            except: pass
        if exp <= 0: exp = sum(i["sub"] for i in s["items"]) + s.get("dcost", 0)

        ver = ai.verify_receipt(rec.get("raw_text", ""), exp)
        paid = ver.get("amount", 0) or rec.get("amount", 0)

        # Summa umuman o'qilmadi → qo'lda tasdiqlash
        if paid <= 0 and not ver["valid"]:
            kb = [[Btn("✅ To'ladim", callback_data="PY")], [Btn("📸 Qayta", callback_data="PR")]]
            await u.message.reply_text(f"⚠️ Kvitansiya aniq o'qilmadi.\nKutilayotgan: {exp:,.0f} so'm",
                                       reply_markup=KB(kb))
            return PAY

        if paid <= 0:
            paid = exp  # valid, lekin summa o'qilmadi — to'liq deb hisoblaymiz

        # OCR juda katta summa o'qigan bo'lsa (xato o'qish) — qo'lda tasdiqlash
        if exp > 0 and paid > exp * 3:
            kb = [[Btn("✅ To'ladim", callback_data="PY")], [Btn("📸 Qayta", callback_data="PR")]]
            await u.message.reply_text(
                f"⚠️ Summa noaniq o'qildi ({paid:,.0f}).\n"
                f"Kutilayotgan: {exp:,.0f} so'm.\nQayta yuboring yoki tasdiqlang.",
                reply_markup=KB(kb))
            return PAY

        diff = paid - exp  # +: ortiqcha, -: kam

        # ── KAM TO'LOV ── invoice qisman to'lanadi, qolganini so'raymiz
        if diff < -500:
            if s.get("inv"):
                odoo.full_payment(s["inv"], paid)  # qisman to'lov
            await u.message.reply_text(ai.payment_msg(paid, exp), parse_mode="Markdown")
            wl.log("paid_partial", cid, f"{paid:.0f}/{exp:.0f}")
            await adm(ctx, f"⚠️ Kam to'lov: {s['cust'].get('name','')} {paid:,.0f}/{exp:,.0f}")
            return PAY  # qolgan to'lovni kutamiz

        # ── ORTIQCHA TO'LOV ── invoice to'liq yopiladi, ortiqcha → mijoz hisobiga kredit
        if diff > 500:
            if s.get("inv"):
                odoo.full_payment(s["inv"], exp)            # invoice to'liq to'landi
            if s.get("pid"):
                odoo.add_customer_credit(s["pid"], diff)    # ortiqcha → kredit (Odoo)
            receipt = odoo.generate_receipt_text(s["inv"]) if s.get("inv") else None
            if receipt:
                await u.message.reply_text(f"```\n{receipt}\n```", parse_mode="Markdown")
            await u.message.reply_text(f"{ai.payment_msg(paid, exp)}\n\n{ai.delivery_wait_msg()}",
                                       parse_mode="Markdown", reply_markup=deliv_kb())
            wl.log("paid_over", cid, f"{paid:.0f} (+{diff:.0f} credit)")
            await adm(ctx, f"💰➕ {s['cust'].get('name','')}: {paid:,.0f} (ortiqcha {diff:,.0f} kredit)")
            return DELIV

        # ── TO'LIQ TO'LOV ──
        if s.get("inv"):
            odoo.full_payment(s["inv"], exp)
        receipt = odoo.generate_receipt_text(s["inv"]) if s.get("inv") else None
        if receipt:
            await u.message.reply_text(f"```\n{receipt}\n```", parse_mode="Markdown")
        await u.message.reply_text(f"{ai.payment_msg(paid, exp)}\n\n{ai.delivery_wait_msg()}",
                                   parse_mode="Markdown", reply_markup=deliv_kb())
        wl.log("paid", cid, f"{paid:.0f}")
        await adm(ctx, f"💰 {s['cust'].get('name', '')}: {paid:,.0f}")
        return DELIV
    except Exception as e:
        log.error(f"Pay: {e}"); await u.message.reply_text("⚠️ Qayta yuboring 📸"); return PAY


async def on_paybtn(u: Update, ctx):
    q = u.callback_query; await q.answer(); cid = q.message.chat_id; s = S(cid)
    if q.data == "PR": await q.edit_message_text("📸 Yangi yuboring:"); return PAY
    if q.data == "PY":
        odoo.connect()
        if s.get("inv"):
            try:
                iv = odoo._r("account.move", "read", [[s["inv"]]], {"fields": ["amount_residual"]})
                amt = iv[0].get("amount_residual", 0) if iv else 0
            except: amt = sum(i["sub"] for i in s.get("items", [])) + s.get("dcost", 0)
            odoo.full_payment(s["inv"], amt)
        await q.edit_message_text("✅ To'lov qabul qilindi!")
        await ctx.bot.send_message(cid, ai.delivery_wait_msg(),
                                   parse_mode="Markdown", reply_markup=deliv_kb())
        return DELIV
    return PAY


# ════════════ DELIVERY ════════════
async def on_deliv_btn(u: Update, ctx):
    """'Qabul qildim' / 'Hali yetmadi' tugmalari."""
    q = u.callback_query; await q.answer(); cid = q.message.chat_id; s = S(cid)
    if q.data == "DOK":
        # Odoo ERP da yetkazib berishni (delivery/picking) tasdiqlash
        delivered = False
        if s.get("so"):
            odoo.connect()
            delivered = odoo.confirm_delivery(s["so"])
        extra = "📦 Yetkazib berish Odoo ERP da tasdiqlandi.\n" if delivered else ""
        await q.edit_message_text(
            f"🎉 *Yakunlandi!*\n🪑 Mebel qabul qilindi ✅\n{extra}Rahmat! 🙏\n\nYana: /start",
            parse_mode="Markdown")
        wl.log("done", cid, "delivered" if delivered else "received"); s["items"] = []
        await adm(ctx, f"🚚✅ {s['cust'].get('name', '')}")
        return CHAT
    if q.data == "DNO":
        await q.edit_message_text(ai.delivery_not_received("hali yetmadi"))
        await adm(ctx, f"⚠️ {s['cust'].get('name', '')}: hali yetmadi")
        return DELIV
    return DELIV


async def on_deliv(u: Update, ctx):
    """Matn orqali javob (tugma o'rniga yozsa ham ishlaydi)."""
    cid = u.effective_chat.id; s = S(cid); msg = u.message.text.strip().lower()
    yes = ["qabul", "oldim", "yetdi", "yetib", "keldi", "ha", "ok", "rahmat", "raxmat"]
    no = ["yetmadi", "kelmadi", "yoq", "hali", "kutaman"]
    if any(w in msg for w in yes):
        delivered = False
        if s.get("so"):
            odoo.connect()
            delivered = odoo.confirm_delivery(s["so"])
        extra = "📦 Yetkazib berish Odoo ERP da tasdiqlandi.\n" if delivered else ""
        await u.message.reply_text(
            f"🎉 *Yakunlandi!*\n🪑 Mebel qabul qilindi ✅\n{extra}Rahmat! 🙏\n\nYana: /start",
            parse_mode="Markdown")
        wl.log("done", cid, "delivered" if delivered else "received"); s["items"] = []
        await adm(ctx, f"🚚✅ {s['cust'].get('name', '')}"); return CHAT
    if any(w in msg for w in no):
        await u.message.reply_text(ai.delivery_not_received(msg))
        await adm(ctx, f"⚠️ {s['cust'].get('name', '')}: {msg}"); return DELIV
    r = ai.chat(msg, customer=s["cust"].get("name", ""), context="Mebel yetkazish kutilmoqda.")
    await u.message.reply_text(r); return DELIV


# ════════════ MAIN ════════════
def main():
    if not TOKEN: print("❌ TOKEN!"); return
    print(f"🪑 Mebel Sales Bot | {datetime.now().strftime('%H:%M:%S')}")
    odoo.connect()
    app = Application.builder().token(TOKEN).build()
    conv = Conv(
        entry_points=[Cmd("start", cmd_start), Cmd("catalog", cmd_catalog)],
        states={
            CHAT:      [Msg(filters.TEXT & ~filters.COMMAND, on_chat), Cbq(on_pick, pattern=r"^B")],
            NEW_PRICE: [Msg(filters.TEXT & ~filters.COMMAND, on_newprice)],
            QTY:       [Msg(filters.TEXT & ~filters.COMMAND, on_qty)],
            CART:      [Cbq(on_cart, pattern=r"^M"), Cbq(on_order, pattern=r"^O")],
            NAME:      [Msg(filters.TEXT & ~filters.COMMAND, on_name)],
            PHONE:     [Msg(filters.TEXT & ~filters.COMMAND, on_phone)],
            ADDR:      [Msg(filters.TEXT & ~filters.COMMAND, on_addr)],
            PAY:       [Msg(filters.PHOTO | filters.Document.ALL, on_pay), Cbq(on_paybtn, pattern=r"^P"),
                        Msg(filters.TEXT & ~filters.COMMAND, on_pay)],
            DELIV:     [Cbq(on_deliv_btn, pattern=r"^D"), Msg(filters.TEXT & ~filters.COMMAND, on_deliv)],
        },
        fallbacks=[Cmd("cancel", cmd_cancel), Cmd("start", cmd_start), Cmd("catalog", cmd_catalog), Cmd("help", cmd_help)],
        allow_reentry=True)
    app.add_handler(conv); app.add_handler(Cmd("help", cmd_help)); app.add_handler(Cmd("myorders", cmd_orders))
    print("🚀 Ready!"); app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
