"""🚀 Entry Point — python run_bot.py"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()


def main():
    print("=" * 50)
    print("  🤖 AI Sales Bot — BTEC L6")
    print("  📋 PDP University | 2026")
    print("=" * 50)

    ok = True
    # Check dependencies
    deps = {"telegram": "python-telegram-bot", "dotenv": "python-dotenv", "PIL": "Pillow"}
    for module, package in deps.items():
        try:
            __import__(module)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} — pip install {package}")
            ok = False

    # Check Groq
    try:
        import groq  # noqa
        print(f"  {'✅' if os.getenv('GROQ_API_KEY') else '⚠️'} Groq AI")
    except ImportError:
        print("  ⚠️ Groq (pip install groq)")

    # Check env vars
    required = ["TELEGRAM_BOT_TOKEN", "ODOO_URL", "ODOO_DB", "ODOO_USERNAME", "ODOO_API_KEY"]
    for var in required:
        if os.getenv(var):
            print(f"  ✅ {var}")
        else:
            print(f"  ❌ {var} — not set")
            ok = False

    # Test Odoo
    try:
        from odoo_auto_connector import OdooAutoConnector
        o = OdooAutoConnector()
        connected, msg = o.connect()
        print(f"  {'✅' if connected else '❌'} Odoo: {msg}")
    except Exception as e:
        print(f"  ⚠️ Odoo: {e}")

    if not ok:
        print("\n❌ Fix errors above!")
        sys.exit(1)

    print("\n🚀 Starting bot...\n")
    try:
        from telegram_ai_bot import main as bot_main
        bot_main()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
