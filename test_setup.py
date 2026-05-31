"""🧪 python test_setup.py — FINAL"""
import os
from dotenv import load_dotenv
load_dotenv()
print("="*50);print("  🧪 AI RPA BOT TEST");print("="*50)
print("\n🏢 Odoo:")
from odoo_auto_connector import OdooAutoConnector
o=OdooAutoConnector();ok,m=o.connect();print(f"  {'✅' if ok else '❌'} {m}")
if ok:
    c=o.test_connection()
    if c: print(f"  ✅ {c.get('name','')}")
    p=o.get_all_products(5);print(f"  📦 Products: {len(p)}")
    for pr in p: print(f"    - {pr['name']}: {pr['price']:,.0f}")
print("\n📱 Telegram:")
t=os.getenv("TELEGRAM_BOT_TOKEN")
if t:
    print(f"  ✅ Token: {t[:8]}...")
    try:
        import requests;r=requests.get(f"https://api.telegram.org/bot{t}/getMe",timeout=10)
        if r.ok: print(f"  ✅ @{r.json()['result'].get('username','')}")
    except: pass
else: print("  ❌ No token")
print("\n🧠 AI:")
try:
    import groq;print(f"  {'✅' if os.getenv('GROQ_API_KEY') else '⚠️'} Groq")
except: print("  ⚠️ No Groq")
print("\n📸 OCR:")
try: import pytesseract;print(f"  ✅ Tesseract {pytesseract.get_tesseract_version()}")
except: print("  ⚠️ No OCR")
print("\n"+"="*50);print("🚀 python run_bot.py")
