"""🏢 Odoo Connector — FINAL | BTEC L6 | PDP University"""
import os, xmlrpc.client, logging
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
log = logging.getLogger(__name__)

class OdooAutoConnector:
    def __init__(self):
        self.url = os.getenv("ODOO_URL","")
        self.db = os.getenv("ODOO_DB","")
        self.username = os.getenv("ODOO_USERNAME","")
        self.api_key = os.getenv("ODOO_API_KEY","")
        self.uid = None; self.models = None; self._bal = {}

    def connect(self):
        try:
            c = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
            self.uid = c.authenticate(self.db, self.username, self.api_key, {})
            if not self.uid: return False, "Auth failed"
            self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
            return True, f"UID:{self.uid}"
        except Exception as e: return False, str(e)

    def _r(self, m, mt, *a, **k):
        return self.models.execute_kw(self.db, self.uid, self.api_key, m, mt, *a, **k)

    def test_connection(self):
        try: c = self._r('res.company','read',[[1]],{'fields':['name','currency_id']}); return c[0] if c else None
        except: return None

    # ===== PARTNER =====
    def find_or_create_partner(self, name, phone=None, email=None, is_supplier=False):
        try:
            ids = self._r('res.partner','search',[[['name','ilike',name]]],{'limit':1})
            if ids:
                u = {}
                if phone: u['phone'] = phone
                if email: u['email'] = email
                if u:
                    try: self._r('res.partner','write',[ids,u])
                    except: pass
                return ids[0]
            v = {'name':name,'company_type':'person'}
            if phone: v['phone']=phone
            if email: v['email']=email
            if is_supplier: v['supplier_rank']=1
            else: v['customer_rank']=1
            return self._r('res.partner','create',[v])
        except:
            try:
                s={'name':name}
                if is_supplier: s['supplier_rank']=1
                else: s['customer_rank']=1
                return self._r('res.partner','create',[s])
            except: return None

    def find_existing_partner(self, name):
        try:
            ids = self._r('res.partner','search',[[['name','ilike',name]]],{'limit':1})
            if ids: return self._r('res.partner','read',[ids],{'fields':['name','phone','email','id']})[0]
        except: pass
        return None

    def get_partner_balance(self, pid): return self._bal.get(pid, 0)
    def add_partner_balance(self, pid, amt):
        self._bal[pid] = self._bal.get(pid,0) + amt
        log.info(f"Balance +{amt}: #{pid} = {self._bal[pid]}")
    def use_partner_balance(self, pid, amt):
        cur = self._bal.get(pid,0); used = min(cur,amt); self._bal[pid] = cur - used; return used

    # ===== PRODUCT =====
    def get_all_products(self, limit=20):
        try:
            ids = self._r('product.product','search',[[['sale_ok','=',True]]],{'limit':limit})
            if not ids: return []
            d = self._r('product.product','read',[ids],{'fields':['name','list_price','standard_price']})
            return [{'id':p['id'],'name':p['name'],'price':p['list_price'],'cost':p.get('standard_price',0)} for p in d]
        except: return []

    def search_products(self, kw):
        try:
            ids = self._r('product.product','search',[[['name','ilike',kw],['sale_ok','=',True]]],{'limit':10})
            if not ids: return []
            d = self._r('product.product','read',[ids],{'fields':['name','list_price','standard_price']})
            return [{'id':p['id'],'name':p['name'],'price':p['list_price'],'cost':p.get('standard_price',0)} for p in d]
        except: return []

    def get_product_info(self, pid):
        try: d = self._r('product.product','read',[[pid]],{'fields':['name','list_price','standard_price']}); return d[0] if d else None
        except: return None

    def find_or_create_product(self, name, price=0.0):
        try:
            ids = self._r('product.product','search',[[['name','=',name]]])
            if ids: return ids[0]
            return self._r('product.product','create',[{'name':name,'list_price':price,'type':'consu','sale_ok':True,'purchase_ok':True}])
        except: return None

    # ===== QUOTATION =====
    def create_quotation(self, partner_id, lines):
        try:
            ol = []
            for l in lines:
                pid = self.find_or_create_product(l['product_name'], l.get('price',0))
                if pid: ol.append((0,0,{'product_id':pid,'product_uom_qty':l['quantity'],'price_unit':l['price']}))
            if not ol: return None, "No products"
            qid = self._r('sale.order','create',[{'partner_id':partner_id,'date_order':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'order_line':ol}])
            info = self._r('sale.order','read',[[qid]],{'fields':['name','amount_total']})
            log.info(f"Quotation: #{qid}")
            return qid, info[0] if info else {'name':f'Q-{qid}'}
        except Exception as e: return None, str(e)

    # ===== FULL CONFIRM: SO → Invoice → POST → Delivery =====
    def full_confirm_order(self, so_id):
        r = {'so_name':'','inv_id':None,'inv_name':'N/A','total':0,'state':'error'}
        log.info(f"[1] Confirm SO {so_id}")
        try: self._r('sale.order','action_confirm',[[so_id]])
        except Exception as e: log.error(f"SO: {e}"); return r
        so = self._r('sale.order','read',[[so_id]],{'fields':['name','amount_total']})
        if so: r['so_name']=so[0].get('name',''); r['total']=so[0].get('amount_total',0)

        log.info(f"[2] Invoice")
        inv = self._mk_inv(so_id)
        if inv:
            r['inv_id'] = inv
            log.info(f"[3] POST {inv}")
            self._post(inv)
            ii = self._r('account.move','read',[[inv]],{'fields':['name','amount_total','state','payment_state']})
            if ii:
                r['inv_name']=ii[0].get('name',''); r['total']=ii[0].get('amount_total',r['total'])
                r['state']=ii[0].get('state','draft')
                log.info(f"Invoice: {ii[0].get('name')} st={ii[0].get('state')} pay={ii[0].get('payment_state')}")
        log.info(f"[4] Delivery")
        self._deliver(so_id)
        return r

    # ===== FULL PAYMENT: POST → Pay → IN PAYMENT =====
    def full_payment(self, inv_id, amount=0):
        if not inv_id: return False, "No inv"
        log.info(f"Payment: inv={inv_id} amt={amount}")
        self._post(inv_id)
        try:
            inv = self._r('account.move','read',[[inv_id]],{'fields':['amount_residual','partner_id','state','payment_state','name']})
            if not inv: return False, "Not found"
            inv = inv[0]
            log.info(f"  {inv.get('name')}: st={inv.get('state')} pay={inv.get('payment_state')} res={inv.get('amount_residual')}")
            if inv.get('payment_state') in ('paid','in_payment'): return True, "Already paid"
            if inv.get('state') != 'posted': self._post(inv_id)
            amt = amount if amount > 0 else inv.get('amount_residual',0)
            if amt <= 0: return False, "Amt=0"
            jid = self._jrn('bank') or self._jrn('cash')
            if not jid: return False, "No journal"
            try:
                ctx = {'active_model':'account.move','active_ids':[inv_id]}
                w = self._r('account.payment.register','create',[{'amount':amt,'journal_id':jid}],{'context':ctx})
                self._r('account.payment.register','action_create_payments',[[w]],{'context':ctx})
                log.info(f"  Paid(wizard): {amt}"); return True, f"Paid {amt}"
            except Exception as e1:
                log.warning(f"  Wizard: {e1}")
                try:
                    p = self._r('account.payment','create',[{'payment_type':'inbound','partner_type':'customer','partner_id':inv['partner_id'][0],'amount':amt,'journal_id':jid}])
                    self._r('account.payment','action_post',[[p]]); log.info(f"  Paid(manual): {amt}"); return True, f"Manual {amt}"
                except Exception as e2: log.error(f"  Manual: {e2}"); return False, str(e2)
        except Exception as e: return False, str(e)

    # ===== RECEIPT TEXT =====
    def generate_receipt_text(self, inv_id):
        try:
            inv = self._r('account.move','read',[[inv_id]],{'fields':['name','partner_id','amount_total','amount_untaxed','amount_tax','state','payment_state','invoice_date','invoice_line_ids']})
            if not inv: return None
            inv = inv[0]
            lines = ""
            if inv.get('invoice_line_ids'):
                ld = self._r('account.move.line','read',[inv['invoice_line_ids']],{'fields':['name','quantity','price_unit','price_subtotal']})
                for l in ld:
                    if l.get('price_subtotal',0) > 0:
                        lines += f"  {l.get('name','?')}\n  {l.get('quantity',0)} x {l.get('price_unit',0):,.0f} = {l.get('price_subtotal',0):,.0f}\n"
            co = os.getenv("COMPANY_NAME","Company"); bk = os.getenv("BANK_NAME","Bank"); ac = os.getenv("BANK_ACCOUNT","0000")
            return (f"{'='*32}\n  📄 CHEK / INVOICE\n{'='*32}\n🏢 {co}\n📋 {inv.get('name','')}\n📅 {inv.get('invoice_date','Bugun')}\n"
                    f"👤 {inv['partner_id'][1] if inv.get('partner_id') else ''}\n{'─'*32}\n📦 MAHSULOTLAR:\n{lines}{'─'*32}\n"
                    f"💰 Summa: {inv.get('amount_untaxed',0):,.0f}\n📊 Soliq: {inv.get('amount_tax',0):,.0f}\n{'─'*32}\n"
                    f"💵 JAMI: {inv.get('amount_total',0):,.0f}\n📊 {(inv.get('payment_state','') or '').upper()}\n{'='*32}\n🏦 {bk} | {ac}\n{'='*32}")
        except: return None

    # ===== INTERNAL =====
    def _mk_inv(self, so_id):
        ctx = {'active_ids':[so_id],'active_model':'sale.order'}
        try:
            w = self._r('sale.advance.payment.inv','create',[{'advance_payment_method':'delivered'}],{'context':ctx})
            self._r('sale.advance.payment.inv','create_invoices',[[w]],{'context':ctx})
            i = self._inv_id(so_id)
            if i: log.info(f"  Inv(wiz): {i}"); return i
        except Exception as e: log.warning(f"  Inv wiz: {e}")
        try:
            self._r('sale.order','action_create_invoice',[[so_id]])
            i = self._inv_id(so_id)
            if i: log.info(f"  Inv(dir): {i}"); return i
        except Exception as e: log.warning(f"  Inv dir: {e}")
        try:
            so = self._r('sale.order','read',[[so_id]],{'fields':['partner_id','name','order_line']})[0]
            ols = self._r('sale.order.line','read',[so['order_line']],{'fields':['product_id','product_uom_qty','price_unit','name']})
            il = [(0,0,{'product_id':ol['product_id'][0] if ol.get('product_id') else False,'quantity':ol.get('product_uom_qty',1),'price_unit':ol.get('price_unit',0),'name':ol.get('name','')}) for ol in ols]
            i = self._r('account.move','create',[{'move_type':'out_invoice','partner_id':so['partner_id'][0],'invoice_origin':so.get('name',''),'invoice_line_ids':il}])
            log.info(f"  Inv(man): {i}"); return i
        except Exception as e: log.error(f"  Inv man: {e}"); return None

    def _inv_id(self, so_id):
        try:
            so = self._r('sale.order','read',[[so_id]],{'fields':['invoice_ids']})
            ids = so[0].get('invoice_ids',[]) if so else []; return ids[-1] if ids else None
        except: return None

    def _post(self, inv_id):
        try:
            s = self._r('account.move','read',[[inv_id]],{'fields':['state']})
            if s and s[0].get('state')=='posted': return True
        except: pass
        for lb, fn in [("post", lambda: self._r('account.move','action_post',[[inv_id]])),
                       ("force", lambda: self._r('account.move','action_post',[[inv_id]],{'context':{'force_post':True}})),
                       ("write", lambda: self._r('account.move','write',[[inv_id],{'state':'posted'}]))]:
            try: fn(); log.info(f"  Posted({lb})"); return True
            except Exception as e: log.warning(f"  Post({lb}): {e}")
        return False

    def _deliver(self, so_id):
        try:
            so = self._r('sale.order','read',[[so_id]],{'fields':['picking_ids']})
            for pk in (so[0].get('picking_ids',[]) if so else []):
                try:
                    d = self._r('stock.picking','read',[[pk]],{'fields':['move_ids','state']})
                    if d and d[0]['state'] not in ('done','cancel'):
                        for mv in d[0].get('move_ids',[]):
                            md = self._r('stock.move','read',[[mv]],{'fields':['product_uom_qty']})
                            if md: self._r('stock.move','write',[[mv],{'quantity':md[0]['product_uom_qty']}])
                        res = self._r('stock.picking','button_validate',[[pk]])
                        if isinstance(res, dict) and res.get('res_model'):
                            try:
                                wm = res['res_model']; wc = res.get('context',{})
                                wi = self._r(wm,'create',[{}],{'context':wc})
                                self._r(wm,'process',[[wi]],{'context':wc})
                            except: pass
                except: pass
        except: pass

    def _jrn(self, t):
        try: ids = self._r('account.journal','search',[[['type','=',t]]],{'limit':1}); return ids[0] if ids else False
        except: return False

    # ===== APP.PY ALIASES =====
    def create_sales_order(self, cu, ls, dt=None):
        cid = self.find_or_create_partner(cu)
        if not cid: return None,"No cust"
        return self.create_quotation(cid, ls)
    def confirm_sales_order(self, s):
        try: self._r('sale.order','action_confirm',[[s]]); return True,"OK"
        except Exception as e: return False, str(e)
    def create_sales_invoice_from_so(self, s):
        i = self._mk_inv(s)
        if i: self._post(i); d = self._r('account.move','read',[[i]],{'fields':['name','amount_total']}); return i, d[0] if d else {}
        return None, "N/A"
    def post_and_pay_invoice(self, i): self._post(i); return True,"OK"
    def create_purchase_order(self, v, ls, dt=None):
        vid = self.find_or_create_partner(v, is_supplier=True)
        if not vid: return None,"No ven"
        return self.create_quotation(vid, ls)
    def confirm_purchase_order(self, p):
        try: self._r('purchase.order','button_confirm',[[p]]); return True,"OK"
        except Exception as e: return False, str(e)
    def create_vendor_bill_from_po(self, p):
        try:
            self._r('purchase.order','action_create_invoice',[[p]])
            po = self._r('purchase.order','read',[[p]],{'fields':['invoice_ids']})
            ids = po[0].get('invoice_ids',[]) if po else []
            return (ids[-1],"OK") if ids else (None,"N/A")
        except Exception as e: return None, str(e)
    def confirm_quotation(self, q): return self.confirm_sales_order(q)
