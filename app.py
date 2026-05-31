"""🖥️ Dashboard — FINAL | streamlit run app.py | BTEC L6"""
import streamlit as st,pandas as pd,time
from datetime import datetime
from odoo_auto_connector import OdooAutoConnector
from workflow_logger import WorkflowLogger
st.set_page_config(page_title="AI RPA Bot",page_icon="🤖",layout="wide")
if 'o' not in st.session_state:
    st.session_state.o=OdooAutoConnector();st.session_state.c=False;st.session_state.ops=[];st.session_state.w=WorkflowLogger()
o=st.session_state.o;w=st.session_state.w
with st.sidebar:
    st.markdown("## ⚙️ Status")
    if st.button("🔌 Connect",use_container_width=True):
        ok,m=o.connect();st.session_state.c=ok
        (st.success if ok else st.error)(m)
        if ok:
            c=o.test_connection()
            if c: st.info(f"📋 {c.get('name','')}")
    st.success("✅") if st.session_state.c else st.error("❌")
st.markdown("# 🤖 AI-Powered Odoo RPA Bot")
st.caption("BTEC L6 | PDP University | 2026 | Groq AI + Telegram + Odoo")
st.divider()
t1,t2,t3=st.tabs(["📤 Sales","📊 Dashboard","📱 Logs"])
with t1:
    if not st.session_state.c: st.error("Connect first!")
    else:
        cu=st.text_input("Customer","ACME",key="sc");dt=st.date_input("Date",key="sd")
        n=st.number_input("Items",1,10,1,key="sn");items=[]
        for i in range(int(n)):
            a,b,c3=st.columns(3)
            items.append({'product_name':a.text_input("Product",f"P{i+1}",key=f"sp{i}"),
                'quantity':b.number_input("Qty",1,9999,1,key=f"sq{i}"),
                'price':c3.number_input("Price",0.0,9e8,1000.0,key=f"spr{i}")})
        if st.button("🚀 Create & Complete",type="primary",use_container_width=True):
            sid,info=o.create_sales_order(cu,items,str(dt))
            if sid:
                st.success(f"✅ SO #{sid}")
                r=o.full_confirm_order(sid)
                st.success(f"✅ {r.get('so_name','')} | {r.get('inv_name','')} | {r.get('state','')}")
            else: st.error(f"❌ {info}")
with t2:
    ws=w.get_today_stats()
    if ws: st.json(ws)
    else: st.info("Bot ishga tushganda statistika ko'rinadi.")
with t3:
    logs=w.get_operations_log(50)
    if logs: st.dataframe(pd.DataFrame(logs),use_container_width=True)
    else: st.info("Loglar yo'q.")
st.divider();st.caption("AI RPA Bot FINAL | BTEC L6 | PDP University 2026")
