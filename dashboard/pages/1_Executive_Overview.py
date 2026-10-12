import streamlit as st

st.set_page_config(page_title="Executive Overview", page_icon="📈", layout="wide")
st.title("Executive Overview")

st.info("In a production environment, this page would aggregate predictions across the entire active customer base stored in the database.")

col1, col2, col3 = st.columns(3)
col1.metric("Total Active Customers (Mock)", "5,432")
col2.metric("High Risk Customers", "440", "8.1%", delta_color="inverse")
col3.metric("Annual Revenue at Risk", "$420,500")

st.markdown("### Risk Distribution")
st.bar_chart({"Low Risk": 4000, "Medium Risk": 992, "High Risk": 440})
