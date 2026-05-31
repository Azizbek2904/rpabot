"""
🧠 AI Engine — Groq (Llama 3.3 70B) — FINAL
Author: BTEC L6 | PDP University
"""
import os, re, logging
from dotenv import load_dotenv
load_dotenv()
log = logging.getLogger(__name__)

GROQ_KEY = os.getenv("GROQ_API_KEY")
HAS_AI = False
client = None
try:
    from groq import Groq
    if GROQ_KEY:
        client = Groq(api_key=GROQ_KEY)
        HAS_AI = True
        log.info("Groq AI ready")
except ImportError:
    log.warning("pip install groq")

DELIVERY = {
    'toshkent': 15000, 'samarqand': 35000, 'buxoro': 40000,
    'andijon': 45000, 'fargona': 45000, 'namangan': 45000,
    'navoiy': 50000, 'qashqadaryo': 55000, 'xorazm': 55000,
    'sirdaryo': 30000, 'jizzax': 35000, 'default': 40000,
}


class AIEngine:
    def __init__(self, company_name="", min_margin=10):
        self.company = company_name or os.getenv("COMPANY_NAME", "Smart Sales")
        self.min_margin = min_margin

    def chat(self, msg, products="", customer="", context="", history=""):
        if not HAS_AI: return self._simple(msg)
        system = (
            f'Sen — "{self.company}" savdo menejeri. O\'zbek tilida gaplash.\n'
            f'Professional, samimiy, do\'stona. Har qanday savolga javob ber.\n'
            f'Narx so\'ralsa — faqat sotish narxini ayt. HECH QACHON foyda/tannarx/margin aytma.\n'
            f'Chegirma so\'ralsa — "rahbar bilan maslahatlashaman" de.\n'
            f'Buyurtma tayyor bo\'lsa javobga BUYURTMA_TAYYOR qo\'sh.\n'
            f'Qisqa (2-5 qator), emoji ishlat.\n\n'
            f'MAHSULOTLAR: {products or "Yo\'q"}\n'
            f'MIJOZ: {customer or "Yangi"}\nHOLAT: {context or "Suhbat"}'
        )
        messages = [{"role": "system", "content": system}]
        if history:
            for line in history.split("\n")[-10:]:
                line = line.strip()
                if line.startswith("M:"): messages.append({"role": "user", "content": line[2:].strip()})
                elif line.startswith("B:"): messages.append({"role": "assistant", "content": line[2:].strip()})
        messages.append({"role": "user", "content": msg})
        try:
            r = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages, max_tokens=300, temperature=0.7)
            t = r.choices[0].message.content.strip()
            return t if t else self._simple(msg)
        except Exception as e:
            log.error(f"AI: {e}"); return self._simple(msg)

    def _simple(self, msg):
        m = msg.lower()
        if any(w in m for w in ['salom','hello','hi','assalom']): return f"Assalomu alaykum! 👋 Men {self.company} botiman. Nima kerak?"
        if any(w in m for w in ['narx','qancha','necha']): return "Mahsulot nomini yozing — narxini aytaman! 📦"
        if any(w in m for w in ['kerak','olaman','bormi','buyurtma']): return "/catalog bosing yoki mahsulot nomini yozing! 🛒"
        if any(w in m for w in ['rahmat','raxmat']): return "Sizga ham rahmat! 🙏"
        if any(w in m for w in ['manzil','yetkazish','dostavka']): return "Manzilni yozing — narxini aytaman! 🚚"
        return "Tushundim! 😊 /catalog bosing yoki nomini yozing."

    def analyze_price(self, cost, sell, qty=1):
        if cost <= 0: return {'ok': True, 'margin': 100, 'profit': sell * qty}
        margin = ((sell - cost) / cost) * 100
        return {'ok': margin >= self.min_margin, 'margin': round(margin, 1),
                'profit': round((sell - cost) * qty, 2)}

    def delivery_cost(self, addr):
        a = addr.lower()
        for c, p in DELIVERY.items():
            if c in a: return p, c.capitalize()
        return DELIVERY['default'], "Boshqa"

    def verify_receipt(self, text, expected, so=""):
        r = {'valid': False, 'amount': 0, 'confidence': 0}
        if not text: return r
        r['amount'] = self._amt(text)
        sc = 0
        if r['amount'] > 0 and expected > 0:
            if abs(r['amount'] - expected) <= expected * 0.1: sc += 4
            elif r['amount'] >= expected: sc += 3
            elif r['amount'] > 0: sc += 1
        for k in ['bank','kapital','uzcard','humo','hisob','mfo']:
            if k in text.lower(): sc += 1; break
        if re.search(r'\d{2}[./]\d{2}[./]\d{4}', text): sc += 1
        for k in ['muvaffaqiyatli','successful','tasdiqlandi']:
            if k in text.lower(): sc += 2; break
        r['confidence'] = min(sc / 8, 1.0)
        r['valid'] = sc >= 3
        if HAS_AI and not r['valid'] and r['amount'] > 0:
            try:
                rr = client.chat.completions.create(model="llama-3.3-70b-versatile",
                    messages=[{"role":"user","content":f"Bank kvitansiyasi. Haqiqiymi? Summa ~{expected}. Matn: {text[:300]}. HA yoki YO'Q:"}], max_tokens=10)
                if "ha" in rr.choices[0].message.content.lower(): r['valid']=True; r['confidence']=0.7
            except: pass
        return r

    def payment_msg(self, paid, expected):
        d = paid - expected
        if abs(d) < 500: return "✅ To'lov to'liq qabul qilindi!"
        elif d > 0: return f"✅ To'lov qabul qilindi!\n💰 To'langan: {paid:,.0f}\n📦 Buyurtma: {expected:,.0f}\n💳 Ortiqcha: {d:,.0f} — hisobingizga yozildi!"
        else: return f"⚠️ To'lov yetarli emas!\n💰 To'langan: {paid:,.0f}\n📦 Buyurtma: {expected:,.0f}\n❌ Qoldiq: {abs(d):,.0f} — qo'shimcha to'lang."

    def delivery_wait_msg(self):
        return "📦 Buyurtma tayyorlanmoqda.\n\n🚚 Yetib borganda *\"Qabul qildim\"* deb yozing.\n❓ Savol bo'lsa bemalol yozing!"

    def delivery_not_received(self, msg):
        if HAS_AI:
            try:
                r = client.chat.completions.create(model="llama-3.3-70b-versatile",
                    messages=[{"role":"user","content":f"Mijoz buyurtma yetib bormaganini aytmoqda: \"{msg}\". Sabr so'ra, 24 soat de. O'zbekcha, 2-3 qator:"}], max_tokens=100)
                return r.choices[0].message.content.strip()
            except: pass
        return "Tushundim, kuryer yo'lda. 24 soat ichida yetib boradi! 🚚"

    def _amt(self, text):
        for p in [r'(?:summa|amount)\s*[:=]?\s*([\d\s,\.]+)', r'(\d{1,3}(?:[,\s]\d{3})+(?:\.\d{2})?)', r'(\d{5,})']:
            for m in re.findall(p, text, re.IGNORECASE):
                try:
                    v = float(m.replace(',','').replace(' ',''))
                    if v > 1000: return v
                except: continue
        return 0
