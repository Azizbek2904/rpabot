"""🧪 Test Setup — python test_setup.py"""
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 50)
print("  🧪 AI RPA Bot — Connection Test")
print("=" * 50)

# Odoo
print("\n🏢 Odoo ERP:")
from odoo_auto_connector import OdooAutoConnector
o = OdooAutoConnector()
ok, msg = o.connect()
print(f"  {'✅' if ok else '❌'} {msg}")
if ok:
    company = o.test_connection()
    if company:
        print(f"  ✅ Company: {company.get('name', '')}")
    products = o.get_all_products(5)
    print(f"  📦 Products: {len(products)}")
    for p in products:
        print(f"    - {p['name']}: {p['price']:,.0f} so'm")

# Telegram
print("\n📱 Telegram:")
token = os.getenv("TELEGRAM_BOT_TOKEN")
if token:
    print(f"  ✅ Token: {token[:8]}...")
    try:
        import requests
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        if r.ok:
            print(f"  ✅ Bot: @{r.json()['result'].get('username', '')}")
    except Exception:
        pass
else:
    print("  ❌ No token")

# AI
print("\n🧠 AI Engine:")
try:
    import groq  # noqa
    key = os.getenv("GROQ_API_KEY")
    print(f"  {'✅' if key else '⚠️'} Groq {'(key set)' if key else '(no key)'}")
except ImportError:
    print("  ⚠️ Groq not installed")

# OCR
print("\n📸 OCR Engine:")
try:
    import pytesseract
    version = pytesseract.get_tesseract_version()
    print(f"  ✅ Tesseract {version}")
except Exception:
    print("  ⚠️ Tesseract not available")

print("\n" + "=" * 50)
print("🚀 Run: python run_bot.py")
