"""🚀 python run_bot.py — FINAL"""
import os,sys
from dotenv import load_dotenv
load_dotenv()
def main():
    print("="*50);print("  🤖 AI Sales Bot FINAL");print("  📋 BTEC L6 | PDP University");print("="*50)
    ok=True
    for m,p in{'telegram':'python-telegram-bot','dotenv':'python-dotenv','PIL':'Pillow'}.items():
        try:__import__(m);print(f"  ✅ {p}")
        except:print(f"  ❌ {p}");ok=False
    try:import groq;print(f"  {'✅' if os.getenv('GROQ_API_KEY') else '⚠️'} Groq AI")
    except:print("  ⚠️ Groq (pip install groq)")
    for v in['TELEGRAM_BOT_TOKEN','ODOO_URL','ODOO_DB','ODOO_USERNAME','ODOO_API_KEY']:
        if os.getenv(v):print(f"  ✅ {v}")
        else:print(f"  ❌ {v}");ok=False
    try:
        from odoo_auto_connector import OdooAutoConnector
        o=OdooAutoConnector();c,m=o.connect();print(f"  {'✅' if c else '❌'} Odoo: {m}")
    except Exception as e:print(f"  ⚠️ {e}")
    if not ok:print("\n❌ Fix errors!");sys.exit(1)
    print("\n🚀 Starting...\n")
    try:
        from telegram_ai_bot import main as bot;bot()
    except KeyboardInterrupt:print("\n🛑 Stopped.")
    except Exception as e:print(f"\n❌ {e}");import traceback;traceback.print_exc()
if __name__=='__main__':main()
