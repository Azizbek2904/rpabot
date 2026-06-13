"""
🏢 Odoo Auto Connector — FULL ERP INTEGRATION
Hammasi Odoo ERP ichida: partner, product, SO, invoice, payment, delivery
Telegram ID orqali mijozni tanish: x_studio_telegram_id
"""
import os
import logging
import xmlrpc.client
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)


class OdooAutoConnector:
    def __init__(self):
        self.url = os.getenv("ODOO_URL", "")
        self.db = os.getenv("ODOO_DB", "")
        self.username = os.getenv("ODOO_USERNAME", "")
        self.api_key = os.getenv("ODOO_API_KEY", "")
        self.uid = None
        self.models = None
        self._tg_field = None  # x_studio_telegram_id mavjudmi: None=noma'lum, True/False=tekshirilgan

    # ═══════ CONNECTION ═══════
    def connect(self):
        if self.uid and self.models:
            try:
                self._r("res.company", "check_access_rights", ["read"], {"raise_exception": False})
                return True, f"UID:{self.uid}"
            except:
                self.uid = None; self.models = None
        try:
            c = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
            self.uid = c.authenticate(self.db, self.username, self.api_key, {})
            if not self.uid:
                return False, "Auth failed"
            self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)
            return True, f"UID:{self.uid}"
        except Exception as e:
            return False, str(e)

    def _ensure(self):
        if not self.uid or not self.models:
            ok, msg = self.connect()
            if not ok:
                raise ConnectionError(f"Odoo: {msg}")

    def _r(self, model, method, *args, **kwargs):
        try:
            return self.models.execute_kw(self.db, self.uid, self.api_key, model, method, *args, **kwargs)
        except xmlrpc.client.Fault:
            # Server/biznes xatosi — qayta urinmaymiz, chaqiruvchi hal qiladi
            raise
        except Exception:
            # Ulanish uzilishi — bir marta qayta ulanib urinamiz
            self.uid = None
            self.connect()
            return self.models.execute_kw(self.db, self.uid, self.api_key, model, method, *args, **kwargs)

    def _has_tg_field(self):
        """x_studio_telegram_id maydoni Odoo'da bormi — bir marta tekshirib keshlaydi."""
        if self._tg_field is None:
            try:
                self._ensure()
                f = self._r("res.partner", "fields_get",
                            [["x_studio_telegram_id"]], {"attributes": ["type"]})
                self._tg_field = bool(f)
            except Exception:
                self._tg_field = False
        return self._tg_field

    def test_connection(self):
        try:
            self._ensure()
            d = self._r("res.company", "read", [[1]], {"fields": ["name", "currency_id"]})
            return d[0] if d else None
        except:
            return None

    # ═══════ PARTNER — TELEGRAM ID ORQALI ═══════
    def find_partner_by_telegram(self, telegram_id):
        """Telegram ID orqali mijozni topish.
        1) x_studio_telegram_id (faqat maydon mavjud bo'lsa)
        2) ref = 'TG<id>' (har doim ishlaydigan zaxira)
        """
        self._ensure()
        tg = str(telegram_id)
        fields = ["name", "phone", "email", "id", "street", "city", "credit", "ref"]

        # 1) Studio maydoni (faqat mavjud bo'lsa — aks holda xato bermaydi)
        if self._has_tg_field():
            try:
                ids = self._r("res.partner", "search",
                    [[["x_studio_telegram_id", "=", tg]]], {"limit": 1})
                if ids:
                    data = self._r("res.partner", "read", [ids],
                                   {"fields": fields + ["x_studio_telegram_id"]})
                    if data:
                        return data[0]
            except Exception as e:
                log.warning(f"Partner by x_studio_telegram_id: {e}")

        # 2) ref zaxira kanali
        try:
            ids = self._r("res.partner", "search",
                [[["ref", "=", f"TG{tg}"]]], {"limit": 1})
            if ids:
                data = self._r("res.partner", "read", [ids], {"fields": fields})
                if data:
                    return data[0]
        except Exception as e:
            log.warning(f"Partner by ref: {e}")
        return None

    def find_or_create_partner(self, name, phone=None, email=None, telegram_id=None):
        """Partner topish yoki yaratish. Telegram ID asosiy kalit."""
        self._ensure()

        # 1. Telegram ID bilan qidirish (asosiy kalit)
        if telegram_id:
            existing = self.find_partner_by_telegram(telegram_id)
            if existing:
                updates = {}
                if name and name != existing.get("name"):
                    updates["name"] = name
                if phone:
                    updates["phone"] = phone
                if email:
                    updates["email"] = email
                if updates:
                    try:
                        self._r("res.partner", "write", [[existing["id"]], updates])
                    except Exception:
                        pass
                return existing["id"]
            # Telegram ID berilgan, lekin topilmadi → YANGI mijoz yaratamiz.
            # (nom bo'yicha "ilike" qidirmaymiz — boshqa Azizbekni ilib olmaslik uchun)
        else:
            # Telegram ID yo'q (masalan dashboarddan) → nom bilan qidirish
            try:
                ids = self._r("res.partner", "search", [[["name", "ilike", name]]], {"limit": 1})
                if ids:
                    return ids[0]
            except Exception:
                pass

        # 2. Yangi mijoz yaratish
        try:
            # Odoo 19'da 'company_type' create'da yozilmaydi — is_company ishlatamiz
            vals = {"name": name, "customer_rank": 1, "is_company": False}
            if phone:
                vals["phone"] = phone
            if email:
                vals["email"] = email
            if telegram_id:
                vals["ref"] = f"TG{telegram_id}"  # ref har doim mavjud — atomik saqlaymiz
            pid = self._r("res.partner", "create", [vals])
            if telegram_id:
                self._link_telegram(pid, telegram_id)  # x_studio (bo'lsa) ham yozamiz
            log.info(f"Partner created in Odoo: #{pid} '{name}' tg={telegram_id}")
            return pid
        except Exception as e:
            log.error(f"Partner create: {e}")
            # Minimal yaratish (eng kam maydon bilan)
            try:
                vals = {"name": name, "customer_rank": 1}
                if telegram_id:
                    vals["ref"] = f"TG{telegram_id}"
                pid = self._r("res.partner", "create", [vals])
                if telegram_id:
                    self._link_telegram(pid, telegram_id)
                log.info(f"Partner created (minimal): #{pid} '{name}' tg={telegram_id}")
                return pid
            except Exception:
                return None

    def _link_telegram(self, partner_id, telegram_id):
        """Telegram ID ni partnerga bog'lash: x_studio (mavjud bo'lsa) + ref (zaxira)."""
        tg = str(telegram_id)
        if self._has_tg_field():
            try:
                self._r("res.partner", "write", [[partner_id], {"x_studio_telegram_id": tg}])
            except Exception:
                pass
        try:
            self._r("res.partner", "write", [[partner_id], {"ref": f"TG{tg}"}])
        except Exception:
            pass

    def find_existing_partner(self, name):
        self._ensure()
        try:
            ids = self._r("res.partner", "search", [[["name", "ilike", name]]], {"limit": 1})
            if ids:
                return self._r("res.partner", "read", [ids], {
                    "fields": ["name", "phone", "email", "id", "street", "city"]
                })[0]
        except:
            pass
        return None

    def update_partner_address(self, partner_id, street, city=""):
        """Odoo ERP da manzilni yangilash."""
        try:
            vals = {}
            if street:
                vals["street"] = street
            if city:
                vals["city"] = city
            if vals:
                self._r("res.partner", "write", [[partner_id], vals])
                return True
        except Exception as e:
            log.warning(f"Address update: {e}")
        return False

    # ═══════ PARTNER BALANCE (ODOO CREDIT) ═══════
    def get_partner_balance(self, partner_id):
        """Odoo ERP dan mijoz balansini olish."""
        try:
            data = self._r("res.partner", "read", [[partner_id]], {"fields": ["credit"]})
            if data:
                return data[0].get("credit", 0)
        except:
            pass
        return 0

    # ═══════ PRODUCT ═══════
    def get_all_products(self, limit=20):
        self._ensure()
        try:
            ids = self._r("product.product", "search", [[["sale_ok", "=", True]]], {"limit": limit})
            if not ids:
                return []
            d = self._r("product.product", "read", [ids], {"fields": ["name", "list_price", "standard_price"]})
            return [{"id": p["id"], "name": p["name"], "price": p["list_price"], "cost": p.get("standard_price", 0)} for p in d]
        except:
            return []

    def search_products(self, keyword):
        self._ensure()
        try:
            ids = self._r("product.product", "search",
                [[["name", "ilike", keyword], ["sale_ok", "=", True]]],
                {"limit": 10})
            if not ids:
                return []
            d = self._r("product.product", "read", [ids], {"fields": ["name", "list_price", "standard_price"]})
            return [{"id": p["id"], "name": p["name"], "price": p["list_price"], "cost": p.get("standard_price", 0)} for p in d]
        except:
            return []

    def get_product_info(self, product_id):
        self._ensure()
        try:
            d = self._r("product.product", "read", [[product_id]], {"fields": ["name", "list_price", "standard_price"]})
            return d[0] if d else None
        except:
            return None

    def find_or_create_product(self, name, price=0.0):
        """Mahsulotni topish yoki Odoo ERP da yaratish. invoice_policy='order' kafolatlanadi."""
        self._ensure()
        try:
            # Aniq nom bilan
            ids = self._r("product.product", "search", [[["name", "=", name]]])
            if ids:
                if price > 0:
                    info = self._r("product.product", "read", [ids[:1]], {"fields": ["list_price"]})
                    if info and info[0].get("list_price", 0) == 0:
                        self._r("product.product", "write", [ids[:1], {"list_price": price}])
                self._ensure_order_policy(ids[0])  # eski mahsulotda ham order qilamiz
                return ids[0]
            # O'xshash qidirish
            ids = self._r("product.product", "search", [[["name", "ilike", name]]], {"limit": 1})
            if ids:
                self._ensure_order_policy(ids[0])
                return ids[0]
            # Yangi yaratish — Odoo ERP da
            pid = self._r("product.product", "create", [{
                "name": name,
                "list_price": price,
                "type": "consu",
                "sale_ok": True,
                "purchase_ok": True,
                "invoice_policy": "order",
            }])
            self._ensure_order_policy(pid)  # shablonga ham majburan yozamiz
            log.info(f"Product created in Odoo: #{pid} '{name}' = {price:,.0f}")
            return pid
        except Exception as e:
            log.error(f"Product: {e}")
            return None

    def _ensure_order_policy(self, product_id):
        """invoice_policy='order' ni product.template ga majburan yozish.
        Odoo 19'da product.product create vals'i shablonga o'tmasligi mumkin —
        shuning uchun to'g'ridan-to'g'ri shablonga yozamiz. Bu 'No items to invoice'
        xatosini bartaraf etadi."""
        try:
            info = self._r("product.product", "read", [[product_id]],
                           {"fields": ["product_tmpl_id", "invoice_policy"]})
            if not info:
                return
            if info[0].get("invoice_policy") == "order":
                return
            tmpl = info[0].get("product_tmpl_id")
            tmpl_id = tmpl[0] if isinstance(tmpl, (list, tuple)) else tmpl
            if tmpl_id:
                self._r("product.template", "write", [[tmpl_id], {"invoice_policy": "order"}])
        except Exception as e:
            log.warning(f"invoice_policy set: {e}")

    # ═══════ QUOTATION ═══════
    def create_quotation(self, partner_id, lines):
        self._ensure()
        try:
            order_lines = []
            for line in lines:
                pid = self.find_or_create_product(line["product_name"], line.get("price", 0))
                if pid:
                    order_lines.append((0, 0, {
                        "product_id": pid,
                        "product_uom_qty": line["quantity"],
                        "price_unit": line["price"],
                    }))
            if not order_lines:
                return None, "No products"
            so_id = self._r("sale.order", "create", [{
                "partner_id": partner_id,
                "date_order": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "order_line": order_lines,
            }])
            info = self._r("sale.order", "read", [[so_id]], {"fields": ["name", "amount_total"]})
            log.info(f"SO created in Odoo: #{so_id}")
            return so_id, info[0] if info else {"name": f"Q-{so_id}"}
        except Exception as e:
            return None, str(e)

    # ═══════ FULL CONFIRM: SO → Invoice → POST → Delivery ═══════
    def full_confirm_order(self, so_id):
        self._ensure()
        r = {"so_name": "", "inv_id": None, "inv_name": "N/A", "total": 0, "state": "error"}

        log.info(f"[1/4] Confirm SO #{so_id}")
        try:
            self._r("sale.order", "action_confirm", [[so_id]])
        except Exception as e:
            log.error(f"SO: {e}"); return r

        so = self._r("sale.order", "read", [[so_id]], {"fields": ["name", "amount_total"]})
        if so:
            r["so_name"] = so[0].get("name", ""); r["total"] = so[0].get("amount_total", 0)

        log.info(f"[2/3] Invoice")
        inv = self._mk_inv(so_id)
        if inv:
            r["inv_id"] = inv
            log.info(f"[3/3] POST #{inv}")
            self._post(inv)
            ii = self._r("account.move", "read", [[inv]], {"fields": ["name", "amount_total", "state", "payment_state"]})
            if ii:
                r["inv_name"] = ii[0].get("name", "")
                r["total"] = ii[0].get("amount_total", r["total"])
                r["state"] = ii[0].get("state", "draft")

        # Delivery shu yerda EMAS — mijoz "Qabul qildim" bosganda tasdiqlanadi
        # (confirm_delivery metodi orqali)
        return r

    # ═══════ FULL PAYMENT ═══════
    def full_payment(self, inv_id, amount=0):
        if not inv_id:
            return False, "No inv"
        self._ensure()
        self._post(inv_id)
        try:
            inv = self._r("account.move", "read", [[inv_id]], {
                "fields": ["amount_residual", "partner_id", "state", "payment_state", "name"]
            })
            if not inv:
                return False, "Not found"
            inv = inv[0]
            if inv.get("payment_state") in ("paid", "in_payment"):
                return True, "Already paid"
            if inv.get("state") != "posted":
                self._post(inv_id)

            amt = amount if amount > 0 else inv.get("amount_residual", 0)
            if amt <= 0:
                return False, "Amt=0"

            jid = self._jrn("bank") or self._jrn("cash")
            if not jid:
                return False, "No journal"

            # Method 1: Wizard
            try:
                ctx = {"active_model": "account.move", "active_ids": [inv_id]}
                w = self._r("account.payment.register", "create", [{"amount": amt, "journal_id": jid}], {"context": ctx})
                self._r("account.payment.register", "action_create_payments", [[w]], {"context": ctx})
                log.info(f"  Paid(wizard): {amt}")
                return True, f"Paid {amt}"
            except Exception as e1:
                log.warning(f"  Wizard: {e1}")

            # Method 2: Direct
            try:
                pid = inv["partner_id"][0] if inv.get("partner_id") else False
                p = self._r("account.payment", "create", [{
                    "payment_type": "inbound", "partner_type": "customer",
                    "partner_id": pid, "amount": amt, "journal_id": jid,
                }])
                self._action_post("account.payment", p)
                log.info(f"  Paid(direct): {amt}")
                return True, f"Direct {amt}"
            except Exception as e2:
                return False, str(e2)
        except Exception as e:
            return False, str(e)

    # ═══════ CUSTOMER CREDIT (ortiqcha to'lov) ═══════
    def add_customer_credit(self, partner_id, amount):
        """Ortiqcha to'langan summani mijoz hisobiga kredit sifatida yozish.
        Odoo'da inbound payment yaratiladi — mijozda foydalanilmagan kredit qoladi."""
        if not partner_id or amount <= 0:
            return False
        try:
            self._ensure()
            jid = self._jrn("bank") or self._jrn("cash")
            if not jid:
                return False
            p = self._r("account.payment", "create", [{
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": partner_id,
                "amount": amount,
                "journal_id": jid,
            }])
            self._action_post("account.payment", p)
            log.info(f"Customer credit: partner #{partner_id} +{amount:,.0f}")
            return True
        except Exception as e:
            log.warning(f"Add credit: {e}")
            return False

    def _action_post(self, model, rec_id):
        """action_post — saas-trial None javobni marshal qila olmasligi mumkin.
        Bunday Fault'da post BAJARILGAN bo'ladi (faqat javob serializatsiyasi yiqilgan),
        shuning uchun uni xato deb hisoblamaymiz."""
        try:
            self._r(model, "action_post", [[rec_id]])
            return True
        except xmlrpc.client.Fault as f:
            msg = str(f)
            if "marshal None" in msg or "allow_none" in msg or "dump_nil" in msg:
                return True  # post amalga oshdi, faqat javob bo'sh edi
            raise

    # ═══════ RECEIPT ═══════
    def generate_receipt_text(self, inv_id):
        try:
            self._ensure()
            inv = self._r("account.move", "read", [[inv_id]], {
                "fields": ["name", "partner_id", "amount_total", "amount_untaxed",
                           "amount_tax", "state", "payment_state", "invoice_date", "invoice_line_ids"]
            })
            if not inv:
                return None
            inv = inv[0]
            lines = ""
            if inv.get("invoice_line_ids"):
                ld = self._r("account.move.line", "read", [inv["invoice_line_ids"]], {
                    "fields": ["name", "quantity", "price_unit", "price_subtotal"]
                })
                for l in ld:
                    if l.get("price_subtotal", 0) > 0:
                        lines += f"  {l.get('name', '?')}\n  {l.get('quantity', 0)} x {l.get('price_unit', 0):,.0f} = {l.get('price_subtotal', 0):,.0f}\n"

            co = os.getenv("COMPANY_NAME", "Company")
            bk = os.getenv("BANK_NAME", "Bank")
            ac = os.getenv("BANK_ACCOUNT", "0000")
            partner = inv["partner_id"][1] if inv.get("partner_id") else ""
            pay_st = (inv.get("payment_state", "") or "").upper()

            return (
                f"{'=' * 32}\n  📄 CHEK / INVOICE\n{'=' * 32}\n"
                f"🏢 {co}\n📋 {inv.get('name', '')}\n📅 {inv.get('invoice_date', 'Bugun')}\n"
                f"👤 {partner}\n{'─' * 32}\n📦 MAHSULOTLAR:\n{lines}{'─' * 32}\n"
                f"💰 Summa: {inv.get('amount_untaxed', 0):,.0f}\n📊 Soliq: {inv.get('amount_tax', 0):,.0f}\n{'─' * 32}\n"
                f"💵 JAMI: {inv.get('amount_total', 0):,.0f}\n📊 {pay_st}\n{'=' * 32}\n🏦 {bk} | {ac}\n{'=' * 32}"
            )
        except:
            return None

    # ═══════ GET CUSTOMER ORDERS FROM ODOO ═══════
    def get_partner_orders(self, partner_id, limit=5):
        """Mijozning oxirgi buyurtmalarini Odoo ERP dan olish."""
        try:
            ids = self._r("sale.order", "search",
                [[["partner_id", "=", partner_id]]], {"limit": limit, "order": "id desc"})
            if not ids:
                return []
            return self._r("sale.order", "read", [ids], {
                "fields": ["name", "amount_total", "state", "date_order"]
            })
        except:
            return []

    # ═══════ INTERNAL ═══════
    def _mk_inv(self, so_id):
        ctx = {"active_ids": [so_id], "active_model": "sale.order"}
        # Usul 1: Standart wizard (invoice_policy='order' bo'lsa ishlaydi)
        try:
            w = self._r("sale.advance.payment.inv", "create",
                        [{"advance_payment_method": "delivered"}], {"context": ctx})
            self._r("sale.advance.payment.inv", "create_invoices", [[w]], {"context": ctx})
            i = self._inv_id(so_id)
            if i:
                log.info(f"  Invoice (wizard): #{i}")
                return i
        except Exception as e:
            log.warning(f"  Inv wizard: {e}")
        # Usul 2: Qo'lda account.move yaratish (zaxira — har doim ishlaydi)
        try:
            so = self._r("sale.order", "read", [[so_id]],
                         {"fields": ["partner_id", "name", "order_line"]})[0]
            ols = self._r("sale.order.line", "read", [so["order_line"]],
                          {"fields": ["product_id", "product_uom_qty", "price_unit", "name"]})
            il = [(0, 0, {
                "product_id": ol["product_id"][0] if ol.get("product_id") else False,
                "quantity": ol.get("product_uom_qty", 1),
                "price_unit": ol.get("price_unit", 0),
                "name": ol.get("name", ""),
            }) for ol in ols]
            i = self._r("account.move", "create", [{
                "move_type": "out_invoice", "partner_id": so["partner_id"][0],
                "invoice_origin": so.get("name", ""), "invoice_line_ids": il,
            }])
            log.info(f"  Invoice (manual): #{i}")
            return i
        except Exception as e:
            log.error(f"  Inv manual: {e}")
            return None

    def _inv_id(self, so_id):
        try:
            so = self._r("sale.order", "read", [[so_id]], {"fields": ["invoice_ids"]})
            ids = so[0].get("invoice_ids", []) if so else []
            return ids[-1] if ids else None
        except:
            return None

    def _post(self, inv_id):
        try:
            s = self._r("account.move", "read", [[inv_id]], {"fields": ["state"]})
            if s and s[0].get("state") == "posted":
                return True
        except:
            pass
        try:
            return self._action_post("account.move", inv_id)
        except:
            pass
        try:
            self._r("account.move", "action_post", [[inv_id]], {"context": {"force_post": True}})
            return True
        except:
            return False

    def confirm_delivery(self, so_id):
        """Mijoz 'Qabul qildim' bosganda — Odoo ERP da yetkazib berishni (picking) tasdiqlash."""
        if not so_id:
            return False
        try:
            self._ensure()
            return self._deliver(so_id)
        except Exception as e:
            log.warning(f"confirm_delivery: {e}")
            return False

    def _deliver(self, so_id):
        done_any = False
        try:
            so = self._r("sale.order", "read", [[so_id]], {"fields": ["picking_ids"]})
            for pk in (so[0].get("picking_ids", []) if so else []):
                try:
                    d = self._r("stock.picking", "read", [[pk]], {"fields": ["move_ids", "state"]})
                    if not d or d[0]["state"] in ("done", "cancel"):
                        if d and d[0]["state"] == "done":
                            done_any = True
                        continue
                    # Har bir harakat uchun yetkazilgan miqdorni belgilash
                    for mv in d[0].get("move_ids", []):
                        md = self._r("stock.move", "read", [[mv]], {"fields": ["product_uom_qty"]})
                        if md:
                            try:
                                self._r("stock.move", "write", [[mv], {"quantity": md[0]["product_uom_qty"]}])
                            except Exception:
                                pass
                    # Pickingni tasdiqlash (saas None-javobiga chidamli)
                    try:
                        res = self._r("stock.picking", "button_validate", [[pk]])
                        if isinstance(res, dict) and res.get("res_model"):
                            # Backorder/immediate transfer wizard
                            wm = res["res_model"]; wc = res.get("context", {})
                            wi = self._r(wm, "create", [{}], {"context": wc})
                            try:
                                self._r(wm, "process", [[wi]], {"context": wc})
                            except Exception:
                                pass
                        done_any = True
                        log.info(f"  Delivery validated: picking #{pk}")
                    except xmlrpc.client.Fault as f:
                        msg = str(f)
                        if "marshal None" in msg or "allow_none" in msg or "dump_nil" in msg:
                            done_any = True  # tasdiqlash bajarildi, faqat javob bo'sh edi
                            log.info(f"  Delivery validated (void resp): picking #{pk}")
                        else:
                            log.warning(f"  Delivery validate: {f}")
                except Exception as e:
                    log.warning(f"  Picking {pk}: {e}")
        except Exception as e:
            log.warning(f"_deliver: {e}")
        return done_any

    def _jrn(self, t):
        try:
            ids = self._r("account.journal", "search", [[["type", "=", t]]], {"limit": 1})
            return ids[0] if ids else False
        except:
            return False

    # ═══════ ALIASES ═══════
    def create_sales_order(self, customer, lines, dt=None):
        cid = self.find_or_create_partner(customer)
        if not cid: return None, "No cust"
        return self.create_quotation(cid, lines)

    def confirm_sales_order(self, s):
        try: self._r("sale.order", "action_confirm", [[s]]); return True, "OK"
        except Exception as e: return False, str(e)
