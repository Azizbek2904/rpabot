"""🤖 AI Sales Bot — FINAL | BTEC L6 | PDP University"""
import os, io, logging, asyncio
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

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)

CHAT, NAME, PHONE, EMAIL, ADDR, NEW_NAME, NEW_PRICE, QTY, CART, PAY, DELIV = range(11)

odoo = OdooAutoConnector()
ai = AIEngine(min_margin=MIN_M)
ocr = OCRProcessor()
wl = WorkflowLogger()
db = {}

def U(c):
    if c not in db:
        db[c] = dict(cust={}, items=[], pid=None, so=None, inv=None,
                      addr='', dcost=0, bal=0, hist='', cur=None, newname=None)
    return db[c]

async def adm(x, t):
    if ADMIN:
        try: await x.bot.send_message(int(ADMIN), t, parse_mode='Markdown')
        except: pass

def prods_str():
    try:
        odoo.connect()
        ps = odoo.get_all_products(20)
        return "\n".join([f"- {p['name']}: {p['price']:,.0f}" for p in ps]) if ps else ""
    except: return ""

# ============ COMMANDS ============
async def c_start(u: Update, x):
    c = u.effective_chat.id; U(c)['items'] = []; U(c)['cur'] = None
    await u.message.reply_text(
        f"🤖 *Assalomu alaykum!*\n\nMen — *{ai.company}* savdo botiman.\nBemalol yozing! 💬\n\n"
        f"🛒 /catalog — Mahsulotlar\n❓ /help — Yordam", parse_mode='Markdown')
    return CHAT

async def c_help(u: Update, x):
    await u.message.reply_text("💬 Yozing — AI javob beradi\n📦 Nom yozing — topaman\n🛒 /catalog — mahsulotlar\n📋 /myorders — buyurtmalarim\n❌ /cancel — bekor", parse_mode='Markdown')
    return CHAT

async def c_cancel(u: Update, x):
    c = u.effective_chat.id; U(c)['items']=[]; U(c)['cur']=None; U(c)['newname']=None
    await u.message.reply_text("❌ Bekor. Yana yozing! 💬"); return CHAT

async def c_catalog(u: Update, x):
    odoo.connect(); ps = odoo.get_all_products(20)
    if not ps:
        await u.message.reply_text("📦 Bazada mahsulot yo'q. Nomini yozing — topib beramiz!"); return CHAT
    t = "📦 *Mahsulotlar:*\n\n"
    kb = []
    for p in ps:
        t += f"• *{p['name']}* — {p['price']:,.0f} so'm\n"
        kb.append([Btn(f"🛒 {p['name']} — {p['price']:,.0f}", callback_data=f"B{p['id']}_{p['price']}")])
    await u.message.reply_text(t+"\n👆 Tanlang yoki nom yozing!", reply_markup=KB(kb), parse_mode='Markdown')
    return CHAT

async def c_orders(u: Update, x):
    c = u.effective_chat.id; s = U(c)
    if not s.get('items'):
        b = f"\n💳 Balans: {s['bal']:,.0f}" if s.get('bal',0) > 0 else ""
        await u.message.reply_text(f"📋 Buyurtma yo'q.{b}\n/catalog yoki yozing!"); return
    t = sum(i['sub'] for i in s['items'])
    ls = "\n".join([f"  {n+1}. {i['name']} × {i['qty']} = {i['sub']:,.0f}" for n,i in enumerate(s['items'])])
    await u.message.reply_text(f"📋 *Buyurtma:*\n{ls}\n💰 {t:,.0f}", parse_mode='Markdown')

# ============ AI CHAT ============
async def on_chat(u: Update, x):
    c = u.effective_chat.id; m = u.message.text.strip(); s = U(c)
    ctx = ""
    if s['items']: ctx = "Savat: "+", ".join([f"{i['name']}x{i['qty']}" for i in s['items']])
    if s.get('bal',0)>0: ctx += f" Balans: {s['bal']:,.0f}"
    s['hist'] += f"\nM:{m}"
    if len(s['hist'])>2000: s['hist']=s['hist'][-1500:]
    reply = ai.chat(m, prods_str(), s['cust'].get('name',''), ctx, s['hist'])
    s['hist'] += f"\nB:{reply[:150]}"

    if "BUYURTMA_TAYYOR" in reply:
        reply = reply.replace("BUYURTMA_TAYYOR","").strip()
        if reply: await u.message.reply_text(reply)
        if not s['cust'].get('name'):
            await u.message.reply_text("👤 Ismingizni yozing:"); return NAME
        return await go_addr(u, x, c)

    odoo.connect(); found = odoo.search_products(m)
    if found:
        kb = [[Btn(f"🛒 {p['name']} — {p['price']:,.0f}", callback_data=f"B{p['id']}_{p['price']}")] for p in found[:5]]
        await u.message.reply_text(reply+"\n\n🔍 Topildi:", reply_markup=KB(kb)); return CHAT

    buy = ['kerak','olaman','bormi','sotasiz','narxi','qancha','bervor','buyurtma']
    if any(w in m.lower() for w in buy):
        await u.message.reply_text(reply+"\n\n📦 Topib beramiz! Mahsulot *nomini aniq* yozing:", parse_mode='Markdown')
        return NEW_NAME

    await u.message.reply_text(reply); return CHAT

# ============ PRODUCT SELECT ============
async def on_pick(u: Update, x):
    q = u.callback_query; await q.answer()
    c = q.message.chat_id; s = U(c)
    if q.data.startswith("B"):
        d = q.data[1:].split("_"); pid, pr = int(d[0]), float(d[1])
        info = odoo.get_product_info(pid); nm = info['name'] if info else f"#{pid}"
        cost = info.get('standard_price',0) if info else 0
        a = ai.analyze_price(cost, pr); log.info(f"[BACKEND] {nm}: margin={a['margin']}%")
        s['cur'] = {'name':nm,'id':pid,'price':pr}
        await q.edit_message_text(f"📦 *{nm}* — {pr:,.0f} so'm\nNechta kerak?", parse_mode='Markdown'); return QTY
    return CHAT

# ============ NEW PRODUCT ============
async def on_newname(u: Update, x):
    c = u.effective_chat.id; s = U(c); nm = u.message.text.strip()
    odoo.connect(); found = odoo.search_products(nm)
    if found:
        kb = [[Btn(f"🛒 {p['name']} — {p['price']:,.0f}", callback_data=f"B{p['id']}_{p['price']}")] for p in found[:5]]
        await u.message.reply_text(f"🔍 *{nm}* topildi!", reply_markup=KB(kb), parse_mode='Markdown'); return CHAT
    s['newname'] = nm
    await u.message.reply_text(f"📦 *{nm}* — yangi. Narxini yozing:", parse_mode='Markdown'); return NEW_PRICE

async def on_newprice(u: Update, x):
    c = u.effective_chat.id; s = U(c)
    try: pr = float(u.message.text.strip().replace(',','').replace(' ',''))
    except: await u.message.reply_text("⚠️ Raqam yozing:"); return NEW_PRICE
    nm = s.get('newname','Mahsulot'); odoo.connect()
    pid = odoo.find_or_create_product(nm, pr)
    s['cur'] = {'name':nm,'id':pid,'price':pr}; s['newname'] = None
    await u.message.reply_text(f"✅ *{nm}* — {pr:,.0f}\nNechta kerak?", parse_mode='Markdown'); return QTY

# ============ QUANTITY ============
async def on_qty(u: Update, x):
    c = u.effective_chat.id; s = U(c)
    try: q = int(u.message.text.strip()); assert q > 0
    except: await u.message.reply_text("⚠️ Son yozing:"); return QTY
    cur = s.get('cur')
    if not cur: await u.message.reply_text("/catalog bosing!"); return CHAT
    s['items'].append({'name':cur['name'],'pid':cur.get('id'),'qty':q,'price':cur['price'],'sub':q*cur['price']})
    s['cur'] = None
    total = sum(i['sub'] for i in s['items'])
    ls = "\n".join([f"  {n+1}. {i['name']} × {i['qty']} = {i['sub']:,.0f}" for n,i in enumerate(s['items'])])
    b = f"\n💳 Balans: {s['bal']:,.0f}" if s.get('bal',0)>0 else ""
    kb = [[Btn("➕ Yana",callback_data="MA")],[Btn("✅ Buyurtma",callback_data="MD")],[Btn("❌ Bekor",callback_data="MC")]]
    await u.message.reply_text(f"✅ Qo'shildi!\n\n📋 *Buyurtma:*\n{ls}\n💰 *Jami:* {total:,.0f}{b}", reply_markup=KB(kb), parse_mode='Markdown')
    return CART

# ============ CART BUTTONS ============
async def on_cart(u: Update, x):
    q = u.callback_query; await q.answer(); c = q.message.chat_id; s = U(c)
    if q.data=="MA": await q.edit_message_text("🛍️ Nom yozing yoki /catalog:"); return CHAT
    if q.data=="MC": s['items']=[]; await q.edit_message_text("❌ Bekor."); return CHAT
    if q.data=="MD":
        if not s['cust'].get('name'): await q.edit_message_text("👤 Ismingizni yozing:"); return NAME
        return await go_addr(q, x, c)
    return CHAT

# ============ CUSTOMER ============
async def on_name(u: Update, x):
    c = u.effective_chat.id; s = U(c); s['cust']['name'] = u.message.text.strip()
    odoo.connect(); ex = odoo.find_existing_partner(s['cust']['name'])
    if ex:
        s['pid']=ex['id']; s['cust']['phone']=ex.get('phone',''); s['cust']['email']=ex.get('email','')
        s['bal']=odoo.get_partner_balance(ex['id'])
        g = f"👋 *{ex['name']}*, tanidim!"
        if s['bal']>0: g += f"\n💳 Balans: {s['bal']:,.0f}"
        await u.message.reply_text(g, parse_mode='Markdown'); return await go_addr(u, x, c)
    await u.message.reply_text("📱 Telefon:"); return PHONE

async def on_phone(u: Update, x):
    U(u.effective_chat.id)['cust']['phone'] = u.message.text.strip()
    await u.message.reply_text("📧 Email:"); return EMAIL

async def on_email(u: Update, x):
    c = u.effective_chat.id; U(c)['cust']['email'] = u.message.text.strip()
    return await go_addr(u, x, c)

# ============ ADDRESS ============
async def go_addr(src, x, c):
    s = U(c)
    if not s['items']:
        t = "📦 Avval mahsulot tanlang! /catalog"
        if hasattr(src,'edit_message_text'): await src.edit_message_text(t)
        elif hasattr(src,'message'): await src.message.reply_text(t)
        return CHAT
    t = "📍 *Yetkazish manzilingiz?*\n(Shahar, tuman, ko'cha)"
    if hasattr(src,'edit_message_text'): await src.edit_message_text(t, parse_mode='Markdown')
    elif hasattr(src,'message'): await src.message.reply_text(t, parse_mode='Markdown')
    else: await x.bot.send_message(c, t, parse_mode='Markdown')
    return ADDR

async def on_addr(u: Update, x):
    c = u.effective_chat.id; s = U(c); s['addr'] = u.message.text.strip()
    dc, reg = ai.delivery_cost(s['addr']); s['dcost'] = dc
    total = sum(i['sub'] for i in s['items']); grand = total + dc
    bu = min(s.get('bal',0), grand); pay = max(grand - bu, 0)
    ls = "\n".join([f"  📦 {i['name']} × {i['qty']} = {i['sub']:,.0f}" for i in s['items']])
    t = f"📋 *Buyurtma:*\n\n{ls}\n\n💰 Mahsulotlar: {total:,.0f}\n🚚 Yetkazish ({reg}): {dc:,.0f}\n"
    if bu > 0: t += f"💳 Balansdan: -{bu:,.0f}\n"
    t += f"\n💵 *TO'LOV: {pay:,.0f} so'm*\n_(Soliq qo'shilishi mumkin)_"
    kb = [[Btn("✅ TASDIQLASH",callback_data="OY")],[Btn("❌ BEKOR",callback_data="ON")]]
    await u.message.reply_text(t+"\n\nTasdiqlaysizmi?", reply_markup=KB(kb), parse_mode='Markdown'); return CART

# ============ ORDER → ODOO ============
async def on_order(u: Update, x):
    q = u.callback_query; await q.answer(); c = q.message.chat_id; s = U(c)
    if q.data=="ON": s['items']=[]; await q.edit_message_text("❌ Bekor."); return CHAT
    if q.data=="OY":
        await q.edit_message_text("⏳ Buyurtma yaratilmoqda...")
        odoo.connect()
        if not s.get('pid'):
            cu = s['cust']; s['pid'] = odoo.find_or_create_partner(cu['name'], phone=cu.get('phone'), email=cu.get('email'))
        lines = [{'product_name':i['name'],'quantity':i['qty'],'price':i['price']} for i in s['items']]
        if s['dcost']>0: lines.append({'product_name':'Yetkazish','quantity':1,'price':s['dcost']})
        qid, qi = odoo.create_quotation(s['pid'], lines)
        if not qid: await x.bot.send_message(c, f"⚠️ {qi}"); return CHAT
        s['so'] = qid; res = odoo.full_confirm_order(qid); s['inv'] = res.get('inv_id')

        # REAL summa (tax bilan)
        pay = res.get('total',0)
        if s.get('inv'):
            try:
                iv = odoo._r('account.move','read',[[s['inv']]],{'fields':['amount_residual']})
                if iv: pay = iv[0].get('amount_residual', pay)
            except: pass
        bu = min(s.get('bal',0), pay)
        if bu > 0: odoo.use_partner_balance(s['pid'], bu); s['bal'] -= bu; pay = max(pay-bu, 0)

        # Backend foyda
        profit = 0
        for i in s['items']:
            if i.get('pid'):
                info = odoo.get_product_info(i['pid'])
                cost = info.get('standard_price',0) if info else 0
                profit += ai.analyze_price(cost, i['price'], i['qty']).get('profit',0)
        await adm(x, f"📊 {res.get('so_name','')} Foyda:{profit:,.0f}")

        bank = os.getenv("BANK_NAME","Kapitalbank"); acc = os.getenv("BANK_ACCOUNT","2020 0000 1234 5678")
        if pay > 0:
            await x.bot.send_message(c,
                f"🎉 *Buyurtma tasdiqlandi!*\n\n📋 *{res.get('so_name','')}*\n📄 {res.get('inv_name','')}\n📍 {s['addr']}\n\n"
                f"💵 *To'lov: {pay:,.0f} so'm*\n\n🏦 {bank}\n💳 {acc}\n📝 {res.get('so_name','')}\n\n📸 Kvitansiya yuboring!",
                parse_mode='Markdown')
            # Chek
            receipt = odoo.generate_receipt_text(s['inv']) if s.get('inv') else None
            if receipt: await x.bot.send_message(c, f"```\n{receipt}\n```", parse_mode='Markdown')
            wl.log("order", c, res.get('so_name','')); return PAY
        else:
            if s.get('inv'): odoo.full_payment(s['inv'], res.get('total',0))
            await x.bot.send_message(c, f"🎉 *Buyurtma!* 💳 Balansdan to'landi!\n\n"+ai.delivery_wait_msg(), parse_mode='Markdown')
            return DELIV
    return CHAT

# ============ PAYMENT ============
async def on_pay(u: Update, x):
    c = u.effective_chat.id; s = U(c)
    ph = None
    if u.message.photo: ph = u.message.photo[-1]
    elif u.message.document: ph = u.message.document
    if not ph:
        r = ai.chat(u.message.text, customer=s['cust'].get('name',''), context="To'lov kutilmoqda.")
        await u.message.reply_text(r+"\n\n📸 Kvitansiya yuboring!"); return PAY

    await u.message.reply_text("⏳ Tekshirmoqda... 🔍")
    try:
        f = await x.bot.get_file(ph.file_id); fb = await f.download_as_bytearray(); raw = bytes(fb)

        # PDF yoki rasm?
        is_pdf = raw[:5]==b'%PDF-' or (getattr(ph,'file_name','') or '').lower().endswith('.pdf')
        if is_pdf:
            log.info("📄 PDF kvitansiya")
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(raw)) as pdf:
                    txt = "\n".join([p.extract_text() or "" for p in pdf.pages])
                rec = {'amount': ocr._amt(txt), 'raw_text': txt[:500]}
            except: rec = {'amount':0,'raw_text':''}
        else:
            log.info("📸 Rasm kvitansiya"); rec = ocr.process_receipt(raw)

        # Real invoice summa
        odoo.connect(); exp = 0
        if s.get('inv'):
            try:
                iv = odoo._r('account.move','read',[[s['inv']]],{'fields':['amount_residual','amount_total']})
                if iv: exp = iv[0].get('amount_residual',0)
            except: pass
        if exp <= 0: exp = sum(i['sub'] for i in s['items']) + s.get('dcost',0)

        ver = ai.verify_receipt(rec.get('raw_text',''), exp, str(s.get('so','')))
        det = ver.get('amount',0) or rec.get('amount',0)
        log.info(f"OCR: detected={det} expected={exp} valid={ver['valid']}")

        if ver['valid'] or det > 0:
            amt = det if det > 0 else exp; diff = amt - exp
            if diff > 500:
                s['bal'] = s.get('bal',0)+diff
                if s.get('pid'): odoo.add_partner_balance(s['pid'], diff)
            # TO'LOV
            if s.get('inv'):
                pay_amt = min(amt, exp) if exp > 0 else amt
                ok, msg = odoo.full_payment(s['inv'], pay_amt)
                log.info(f"Payment: {ok} {msg}")
            pm = ai.payment_msg(amt, exp)
            await u.message.reply_text(f"{pm}\n\n"+ai.delivery_wait_msg(), parse_mode='Markdown')
            # Chek
            receipt = odoo.generate_receipt_text(s['inv']) if s.get('inv') else None
            if receipt: await u.message.reply_text(f"```\n{receipt}\n```", parse_mode='Markdown')
            wl.log("paid", c, f"{amt}"); await adm(x, f"💰 {s['cust'].get('name','')}: {amt:,.0f}")
            return DELIV
        else:
            kb = [[Btn("✅ To'ladim",callback_data="PY")],[Btn("📸 Qayta",callback_data="PR")]]
            await u.message.reply_text(f"⚠️ Aniq o'qilmadi.\nKutilayotgan: {exp:,.0f}\nTo'ladingizmi?", reply_markup=KB(kb))
            return PAY
    except Exception as e:
        log.error(f"Pay: {e}"); await u.message.reply_text("⚠️ Xato. Qayta yuboring 📸"); return PAY

async def on_paybtn(u: Update, x):
    q = u.callback_query; await q.answer(); c = q.message.chat_id; s = U(c)
    if q.data=="PR": await q.edit_message_text("📸 Yangi yuboring:"); return PAY
    if q.data=="PY":
        odoo.connect()
        if s.get('inv'):
            try:
                iv = odoo._r('account.move','read',[[s['inv']]],{'fields':['amount_residual']})
                amt = iv[0].get('amount_residual',0) if iv else 0
            except: amt = sum(i['sub'] for i in s.get('items',[])) + s.get('dcost',0)
            odoo.full_payment(s['inv'], amt)
        await q.edit_message_text(f"✅ Qabul qilindi!\n\n"+ai.delivery_wait_msg(), parse_mode='Markdown')
        receipt = odoo.generate_receipt_text(s['inv']) if s.get('inv') else None
        if receipt:
            await x.bot.send_message(c, f"```\n{receipt}\n```", parse_mode='Markdown')
        return DELIV

# ============ DELIVERY ============
async def on_deliv(u: Update, x):
    c = u.effective_chat.id; s = U(c); m = u.message.text.strip().lower()
    yes = ['qabul','oldim','yetdi','yetib','keldi','oldi','ha','ok','rahmat','raxmat']
    no = ['yetmadi','kelmadi','yoq','hali','kutaman','bormadi']
    if any(w in m for w in yes):
        await u.message.reply_text("🎉 *Yakunlandi!*\n📦 Qabul qilindi ✅\nRahmat! 🙏\n\nYana: /start 💬", parse_mode='Markdown')
        wl.log("done",c,"OK"); s['items']=[]; await adm(x, f"🚚✅ {s['cust'].get('name','')}"); return CHAT
    if any(w in m for w in no):
        r = ai.delivery_not_received(m); await u.message.reply_text(r)
        await adm(x, f"⚠️ {s['cust'].get('name','')}: {m}"); return DELIV
    r = ai.chat(m, customer=s['cust'].get('name',''), context="Yetkazish kutilmoqda.")
    await u.message.reply_text(r); return DELIV

# ============ MAIN ============
def main():
    if not TOKEN: print("❌ TOKEN!"); return
    print(f"🤖 AI Sales Bot FINAL | {datetime.now().strftime('%H:%M:%S')}"); odoo.connect()
    app = Application.builder().token(TOKEN).build()
    conv = Conv(
        entry_points=[Cmd('start',c_start), Cmd('catalog',c_catalog), Cmd('order',c_catalog)],
        states={
            CHAT:      [Msg(filters.TEXT & ~filters.COMMAND, on_chat), Cbq(on_pick, pattern=r'^B')],
            NEW_NAME:  [Msg(filters.TEXT & ~filters.COMMAND, on_newname)],
            NEW_PRICE: [Msg(filters.TEXT & ~filters.COMMAND, on_newprice)],
            QTY:       [Msg(filters.TEXT & ~filters.COMMAND, on_qty)],
            CART:      [Cbq(on_cart, pattern=r'^M'), Cbq(on_order, pattern=r'^O')],
            NAME:      [Msg(filters.TEXT & ~filters.COMMAND, on_name)],
            PHONE:     [Msg(filters.TEXT & ~filters.COMMAND, on_phone)],
            EMAIL:     [Msg(filters.TEXT & ~filters.COMMAND, on_email)],
            ADDR:      [Msg(filters.TEXT & ~filters.COMMAND, on_addr)],
            PAY:       [Msg(filters.PHOTO|filters.Document.ALL, on_pay), Cbq(on_paybtn, pattern=r'^P'),
                        Msg(filters.TEXT & ~filters.COMMAND, on_pay)],
            DELIV:     [Msg(filters.TEXT & ~filters.COMMAND, on_deliv)],
        },
        fallbacks=[Cmd('cancel',c_cancel), Cmd('start',c_start), Cmd('catalog',c_catalog), Cmd('help',c_help)],
        allow_reentry=True)
    app.add_handler(conv); app.add_handler(Cmd('help',c_help)); app.add_handler(Cmd('myorders',c_orders))
    print("🚀 Ready!"); app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__': main()
