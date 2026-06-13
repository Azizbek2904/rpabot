"""🖥️ Dashboard — FIXED | streamlit run app.py | BTEC L6"""
import streamlit as st
import pandas as pd
from datetime import datetime
from odoo_auto_connector import OdooAutoConnector
from workflow_logger import WorkflowLogger

st.set_page_config(page_title="AI RPA Bot Dashboard", page_icon="🤖", layout="wide")

if "odoo" not in st.session_state:
    st.session_state.odoo = OdooAutoConnector()
    st.session_state.connected = False
    st.session_state.logger = WorkflowLogger()

odoo = st.session_state.odoo
wl = st.session_state.logger

# Sidebar
with st.sidebar:
    st.markdown("## ⚙️ Connection")
    if st.button("🔌 Connect to Odoo", use_container_width=True):
        ok, msg = odoo.connect()
        st.session_state.connected = ok
        (st.success if ok else st.error)(msg)
        if ok:
            company = odoo.test_connection()
            if company:
                st.info(f"📋 {company.get('name', '')}")
    if st.session_state.connected:
        st.success("✅ Connected")
    else:
        st.error("❌ Not connected")

# Header
st.markdown("# 🤖 AI-Powered RPA Sales Bot")
st.caption("BTEC L6 | PDP University | 2026 | Groq AI + Telegram + Odoo")
st.divider()

# Tabs
tab1, tab2, tab3 = st.tabs(["📤 Sales Order", "📊 Dashboard", "📱 Operation Logs"])

with tab1:
    if not st.session_state.connected:
        st.error("⚠️ Connect to Odoo first!")
    else:
        customer = st.text_input("Customer Name", "Test Customer")
        num_items = st.number_input("Number of Items", 1, 10, 1)
        items = []
        for i in range(int(num_items)):
            col1, col2, col3 = st.columns(3)
            items.append({
                "product_name": col1.text_input("Product", f"Product {i+1}", key=f"p{i}"),
                "quantity": col2.number_input("Qty", 1, 9999, 1, key=f"q{i}"),
                "price": col3.number_input("Price", 0.0, 9e8, 10000.0, key=f"pr{i}"),
            })
        if st.button("🚀 Create & Complete Order", type="primary", use_container_width=True):
            with st.spinner("Processing..."):
                sid, info = odoo.create_sales_order(customer, items)
                if sid:
                    st.success(f"✅ SO #{sid} created")
                    result = odoo.full_confirm_order(sid)
                    st.success(
                        f"✅ {result.get('so_name', '')} | "
                        f"{result.get('inv_name', '')} | "
                        f"State: {result.get('state', '')}"
                    )
                    wl.log("dashboard_order", 0, result.get("so_name", ""))
                else:
                    st.error(f"❌ {info}")

with tab2:
    stats = wl.get_today_stats()
    if stats:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Operations", stats.get("total", 0))
        col2.metric("Successful", stats.get("ok", 0))
        col3.metric("Errors", stats.get("error", 0))
        if stats.get("ops"):
            st.bar_chart(pd.DataFrame.from_dict(stats["ops"], orient="index", columns=["Count"]))
    else:
        st.info("📊 Bot ishga tushganda statistika ko'rinadi.")

    all_stats = wl.get_all_stats()
    if all_stats:
        st.subheader("📈 Daily Trend")
        daily = {k: v.get("total", 0) for k, v in all_stats.items()}
        st.line_chart(pd.DataFrame.from_dict(daily, orient="index", columns=["Operations"]))

with tab3:
    logs = wl.get_operations_log(50)
    if logs:
        df = pd.DataFrame(logs)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("📱 Loglar yo'q — bot ishga tushganda paydo bo'ladi.")

st.divider()
st.caption("AI RPA Bot | BTEC L6 | PDP University 2026")
