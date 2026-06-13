"""
🧠 AI Engine — Groq (Llama 3.3 70B) — FURNITURE EDITION
Author: BTEC L6 | PDP University
Mebel do'koni uchun: avtomatik narx, topib berish xizmati
"""
import os
import re
import logging
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
        log.info("✅ Groq AI ready")
except ImportError:
    log.warning("⚠️ pip install groq")

DELIVERY_COSTS = {
    "toshkent": 50000, "samarqand": 150000, "buxoro": 180000,
    "andijon": 200000, "fargona": 200000, "namangan": 200000,
    "navoiy": 220000, "qashqadaryo": 250000, "xorazm": 250000,
    "sirdaryo": 120000, "jizzax": 140000, "surxondaryo": 280000,
}
DEFAULT_DELIVERY = 180000

# Mebel narx uchun bazaviy ma'lumot (AI ga yordam)
FURNITURE_PRICE_GUIDE = {
    "stul": (150000, 800000), "kreslo": (500000, 3000000),
    "stol": (300000, 5000000), "shkaf": (800000, 8000000),
    "divan": (1500000, 15000000), "krovat": (1000000, 10000000),
    "yotoq": (1000000, 10000000), "polka": (200000, 2000000),
    "tumba": (200000, 1500000), "ko'zgu": (150000, 1000000),
    "komod": (500000, 3000000), "pechka": (300000, 2000000),
    "oshxona": (2000000, 15000000), "yumshoq": (1500000, 12000000),
    "ofis": (300000, 5000000), "bolalar": (500000, 5000000),
}


class AIEngine:
    """Mebel do'koni uchun AI savdo menejeri."""

    def __init__(self, company_name="", min_margin=10):
        self.company = company_name or os.getenv("COMPANY_NAME", "Mebel Market")
        self.min_margin = min_margin

    # ───────── CHAT ─────────
    def chat(self, msg, products="", customer="", context="", history=""):
        if not HAS_AI:
            return self._simple(msg)

        system = (
            f'Sen — "{self.company}" MEBEL do\'konining AI savdo menejeri. FAQAT o\'zbek tilida, '
            f'aniq va do\'stona gaplash.\n'
            f'Bizning do\'kon FAQAT mebel sotadi: stol, stul, divan, shkaf, krovat, kreslo, komod, '
            f'tumba, polka, yotoq, oshxona/ofis/bolalar mebeli, ko\'zgu, matras va shunga o\'xshash.\n\n'
            f'QAT\'IY QOIDALAR:\n'
            f'1. Salomlashilsa — o\'zingni tanishtir: "Men {self.company} mebel botiman".\n'
            f'2. Mijoz biror MEBEL so\'rasa (katalogda bo\'lsin yoki bo\'lmasin), javobing OXIRIDA '
            f'alohida qatorda aniq yoz: "MAHSULOT: <mebel nomi>". Bittagina mebel nomini yoz.\n'
            f'3. Agar mebel katalogda bo\'lmasa — "Bizda hozir yo\'q, lekin TOPIB BERAMIZ!" deb ayt, '
            f'baribir MAHSULOT qatorini qo\'sh.\n'
            f'4. Mijoz MEBEL EMAS narsa so\'rasa (telefon, kiyim, oziq-ovqat, texnika, mashina va h.k.) — '
            f'muloyim rad et: "Kechirasiz, biz faqat mebel sotamiz 🪑". MAHSULOT qatorini QO\'SHMA.\n'
            f'5. Narx so\'ralsa — faqat sotish narxini ayt. HECH QACHON foyda/tannarx aytma.\n'
            f'6. Chegirma so\'ralsa — "rahbar bilan maslahatlashaman" de.\n'
            f'7. Mijoz buyurtmani yakunlamoqchi bo\'lsa — javobga BUYURTMA_TAYYOR qo\'sh.\n'
            f'8. Qisqa (2-4 qator), aniq javob ber. Emoji ishlat. Hech qachon o\'ylab topma.\n\n'
            f'KATALOGDAGI MAHSULOTLAR: {products or "Katalog hozircha bo\'sh"}\n'
            f'MIJOZ: {customer or "Yangi"}\nHOLAT: {context or "Suhbat"}'
        )

        messages = [{"role": "system", "content": system}]
        if history:
            for line in history.strip().split("\n")[-10:]:
                line = line.strip()
                if line.startswith("M:"):
                    messages.append({"role": "user", "content": line[2:].strip()})
                elif line.startswith("B:"):
                    messages.append({"role": "assistant", "content": line[2:].strip()})
        messages.append({"role": "user", "content": msg})

        try:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile", messages=messages,
                max_tokens=300, temperature=0.7,
            )
            text = resp.choices[0].message.content.strip()
            return text if text else self._simple(msg)
        except Exception as e:
            log.error(f"AI chat: {e}")
            return self._simple(msg)

    def _simple(self, msg):
        m = msg.lower()
        if any(w in m for w in ["salom", "hello", "hi", "assalom"]):
            return f"Assalomu alaykum! 👋 Men {self.company} mebel botiman. Qanday mebel kerak?"
        if any(w in m for w in ["narx", "qancha", "necha"]):
            return "Mebel nomini yozing — narxini aytaman! 🪑"
        if any(w in m for w in ["kerak", "olaman", "bormi", "buyurtma"]):
            return "Qanday mebel kerak? Nomini yozing yoki /catalog bosing! 🛋️"
        if any(w in m for w in ["rahmat", "raxmat"]):
            return "Sizga ham rahmat! 🙏"
        if any(w in m for w in ["manzil", "yetkazish", "dostavka"]):
            return "Manzilni yozing — yetkazish narxini aytaman! 🚚"
        if any(w in m for w in ["topib", "boshqa", "yo'q", "yoq"]):
            return "Ha, topib beramiz! 🔍 Qanday mebel kerak — nomini yozing!"
        return "Tushundim! 😊 Qanday mebel kerak? Yozing yoki /catalog bosing! 🪑"

    # ───────── MAHSULOT MARKERINI AJRATISH ─────────
    @staticmethod
    def extract_product(reply):
        """AI javobidan 'MAHSULOT: <nom>' qatorini ajratib oladi.
        Qaytaradi: (product_name yoki None, marker olib tashlangan toza javob)."""
        if not reply:
            return None, ""
        product = None
        clean = []
        for line in reply.split("\n"):
            stripped = line.strip()
            up = stripped.upper()
            if up.startswith("MAHSULOT:") or up.startswith("MAHSULOT :"):
                name = stripped.split(":", 1)[1].strip()
                # qavslar/yulduzchalarni tozalash
                name = name.strip(" *_-•·[](){}").strip()
                if name and name not in ("?", "-", "yo'q", "yoq"):
                    product = name
            else:
                clean.append(line)
        return product, "\n".join(clean).strip()

    # ───────── AUTO PRICE ESTIMATION ─────────
    def estimate_furniture_price(self, product_name):
        """Mebel narxini avtomatik baholash — AI yoki bazaviy narxlar asosida."""
        name_lower = product_name.lower()

        # Avval bazaviy narx guiddan tekshir
        for keyword, (min_p, max_p) in FURNITURE_PRICE_GUIDE.items():
            if keyword in name_lower:
                mid_price = (min_p + max_p) // 2
                # O'rtacha narxni qaytarish (yumaloq raqamga)
                rounded = round(mid_price / 50000) * 50000
                if rounded < min_p:
                    rounded = min_p
                log.info(f"Price guide: {product_name} → {rounded:,} (range {min_p:,}-{max_p:,})")
                return rounded

        # AI orqali narx baholash
        if HAS_AI:
            try:
                resp = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{
                        "role": "user",
                        "content": (
                            f"O'zbekistonda '{product_name}' mebeli o'rtacha qancha turadi? "
                            f"So'mda. Faqat RAQAM yoz, hech narsa qo'shma. Masalan: 2500000"
                        ),
                    }],
                    max_tokens=20,
                    temperature=0.3,
                )
                answer = resp.choices[0].message.content.strip()
                # Raqamni ajratib olish
                nums = re.findall(r"[\d,\s]+", answer.replace(" ", ""))
                for n in nums:
                    val = float(n.replace(",", "").replace(" ", ""))
                    if val > 50000:
                        rounded = round(val / 50000) * 50000
                        log.info(f"AI price: {product_name} → {rounded:,}")
                        return rounded
            except Exception as e:
                log.warning(f"AI price estimate: {e}")

        # Default — o'rtacha mebel narxi
        log.info(f"Default price: {product_name} → 1,500,000")
        return 1500000

    # ───────── PRICE ANALYSIS (backend only) ─────────
    def analyze_price(self, cost, sell, qty=1):
        if cost <= 0:
            return {"ok": True, "margin": 100.0, "profit": round(sell * qty, 2)}
        margin = ((sell - cost) / cost) * 100
        return {"ok": margin >= self.min_margin, "margin": round(margin, 1),
                "profit": round((sell - cost) * qty, 2)}

    # ───────── DELIVERY COST ─────────
    def delivery_cost(self, address):
        addr = address.lower().strip()
        for region, price in DELIVERY_COSTS.items():
            if region in addr:
                return price, region.capitalize()
        return DEFAULT_DELIVERY, "Boshqa"

    # ───────── RECEIPT VERIFICATION ─────────
    def verify_receipt(self, text, expected, so_name=""):
        result = {"valid": False, "amount": 0, "confidence": 0.0}
        if not text or not text.strip():
            return result

        result["amount"] = self.extract_amount(text)
        score = 0

        if result["amount"] > 0 and expected > 0:
            ratio = result["amount"] / expected
            if 0.95 <= ratio <= 1.05:
                score += 5
            elif 0.9 <= ratio <= 1.1:
                score += 4
            elif result["amount"] >= expected:
                score += 3
            elif result["amount"] > 0:
                score += 1

        bank_kw = ["bank", "kapital", "uzcard", "humo", "hisob", "mfo", "o'tkazma", "perevod"]
        score += min(sum(1 for k in bank_kw if k in text.lower()), 2)

        if re.search(r"\d{2}[./]\d{2}[./]\d{4}", text):
            score += 1

        success_kw = ["muvaffaqiyatli", "successful", "tasdiqlandi", "bajarildi"]
        if any(w in text.lower() for w in success_kw):
            score += 2

        result["confidence"] = round(min(score / 10, 1.0), 2)
        result["valid"] = score >= 4

        if HAS_AI and not result["valid"] and result["amount"] > 0 and score >= 2:
            try:
                ai_resp = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": f"Bank kvitansiyasi. Haqiqiymi? Summa ~{expected:,.0f}. Matn: {text[:400]}. HA yoki YO'Q:"}],
                    max_tokens=10,
                )
                if "ha" in ai_resp.choices[0].message.content.lower():
                    result["valid"] = True
                    result["confidence"] = max(result["confidence"], 0.7)
            except Exception:
                pass
        return result

    # ───────── MESSAGES ─────────
    def payment_msg(self, paid, expected):
        diff = paid - expected
        if abs(diff) < 500:
            return f"✅ *To'lov to'liq qabul qilindi!*\n💰 {paid:,.0f} so'm"
        elif diff > 0:
            return (f"✅ *To'lov qabul qilindi!*\n"
                    f"💰 To'langan: {paid:,.0f} so'm\n"
                    f"📦 Buyurtma: {expected:,.0f} so'm\n"
                    f"💳 Ortiqcha: *{diff:,.0f} so'm* — hisobingizga kredit qilib yozildi! "
                    f"Keyingi xaridda ishlatasiz. 🎁")
        else:
            return (f"⚠️ *To'lov yetarli emas!*\n"
                    f"💰 To'langan: {paid:,.0f} so'm\n"
                    f"📦 Buyurtma: {expected:,.0f} so'm\n"
                    f"❌ Qolgan: *{abs(diff):,.0f} so'm* — iltimos, qolgan summani ham to'lab, "
                    f"yangi kvitansiya yuboring. 📸")

    def delivery_wait_msg(self):
        return ("📦 Buyurtma tayyorlanmoqda.\n"
                "🚚 Mebel yetib borganda pastdagi *\"✅ Qabul qildim\"* tugmasini bosing.\n"
                "❓ Savol bo'lsa bemalol yozing!")

    def delivery_not_received(self, msg):
        if HAS_AI:
            try:
                resp = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": f'Mijoz mebel yetib bormaganini aytmoqda: "{msg}". Sabr so\'ra, 48 soat de. O\'zbekcha, 2-3 qator:'}],
                    max_tokens=100,
                )
                return resp.choices[0].message.content.strip()
            except Exception:
                pass
        return "Tushundim, mebel tayyorlanmoqda. 48 soat ichida yetib boradi! 🚚"

    @staticmethod
    def extract_amount(text):
        patterns = [
            r"(?:summa|amount|sum|jami|total)\s*[:=]?\s*([\d\s,\.]+)",
            r"(\d{1,3}(?:[,\s]\d{3})+(?:\.\d{2})?)",
            r"(\d{5,})",
        ]
        for pattern in patterns:
            for match in re.findall(pattern, text, re.IGNORECASE):
                try:
                    value = float(match.replace(",", "").replace(" ", ""))
                    if value > 1000:
                        return value
                except (ValueError, AttributeError):
                    continue
        return 0
