import streamlit as st

from dashboard.api_client import get_health

st.set_page_config(
    page_title="Customer Churn Intelligence Platform",
    page_icon="📊",
    layout="wide",
)

st.title("Customer Churn & Retention Intelligence Platform")

st.markdown("""
Welcome to the internal dashboard. Use the sidebar to navigate the different modules:
*   **Executive Overview:** High-level metrics.
*   **Churn Analytics:** View historical data distributions.
*   **Customer Risk Explorer:** View predictions for the customer base.
*   **Customer Explanation:** Deep dive into individual customer SHAP drivers.
*   **Retention Recommendations:** Actionable steps to save at-risk customers.
*   **Revenue Exposure:** Financial risk analysis.
*   **Model Performance:** Metrics and diagnostics for the underlying ML model.
""")

st.subheader("System Status")
with st.spinner("Checking API health..."):
    is_healthy = get_health()
    if is_healthy:
        st.success("API is Online and Connected.")
    else:
        st.error("API is Offline. Please ensure the backend is running.")
