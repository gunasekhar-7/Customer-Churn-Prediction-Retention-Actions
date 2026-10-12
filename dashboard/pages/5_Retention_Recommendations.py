import streamlit as st

from dashboard.api_client import get_health, get_retention_recommendation

st.set_page_config(page_title="Retention Recommendations", page_icon="💡", layout="wide")
st.title("Retention Recommendations")

if not get_health():
    st.error("API is Offline.")
    st.stop()

st.write("This page demonstrates the intelligence engine outputs.")

# Hardcode a sample customer
sample_customer = {
    "customerID": "RISK-100",
    "gender": "Male",
    "SeniorCitizen": 0,
    "Partner": "No",
    "Dependents": "No",
    "tenure": 2,
    "PhoneService": "Yes",
    "MultipleLines": "No",
    "InternetService": "Fiber optic",
    "OnlineSecurity": "No",
    "OnlineBackup": "No",
    "DeviceProtection": "No",
    "TechSupport": "No",
    "StreamingTV": "Yes",
    "StreamingMovies": "Yes",
    "Contract": "Month-to-month",
    "PaperlessBilling": "Yes",
    "PaymentMethod": "Electronic check",
    "MonthlyCharges": 95.0,
    "TotalCharges": "190.0"
}

st.json(sample_customer, expanded=False)

if st.button("Generate Recommendations"):
    with st.spinner("Analyzing..."):
        try:
            result = get_retention_recommendation(sample_customer)

            st.metric("Risk Segment", result["risk_segment"])
            st.metric("Annual Revenue Exposure", f"${result['annual_revenue_exposure']:.2f}")

            st.subheader("Recommended Actions")
            for rec in result["recommendations"]:
                st.info(f"**Action:** {rec['action']}  \n**Reason:** {rec['reason']}")

        except Exception as e:
            st.error(f"Error fetching recommendations: {e}")
