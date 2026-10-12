import streamlit as st

st.set_page_config(page_title="Revenue Exposure", page_icon="💰", layout="wide")
st.title("Revenue Exposure Dashboards")

st.info("In a production system with real-time access to the prediction_records and retention_recommendations tables, this page would display aggregate dollar sums.")

st.markdown("""
### Estimated Exposure
* **Total Exposure (High Risk):** $1,245,000
* **Total Exposure (Medium Risk):** $850,000

### Retention ROI (Simulated)
Assuming a 10% success rate on Medium/High risk interventions:
* **Expected Saved Revenue:** $209,500
* **Estimated Cost of Interventions:** $15,000 (Based on $10 credits)
* **Projected Net ROI:** +1296%
""")
