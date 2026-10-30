import streamlit as st

from dashboard.api_client import get_health, get_retention_recommendation

st.set_page_config(page_title="Retention Recommendations", page_icon="💡", layout="wide")
st.title("Retention Recommendations")

if not get_health():
    st.error("API is Offline.")
    st.stop()

st.write("Enter customer details to generate personalized retention recommendations.")

# Sidebar form with all required fields
st.sidebar.header("Customer Input")

customerID = st.sidebar.text_input("Customer ID", "TEST-1")
gender = st.sidebar.selectbox("Gender", ["Female", "Male"])
SeniorCitizen = st.sidebar.selectbox("Senior Citizen", [0, 1], format_func=lambda x: "Yes" if x == 1 else "No")
Partner = st.sidebar.selectbox("Partner", ["Yes", "No"])
Dependents = st.sidebar.selectbox("Dependents", ["Yes", "No"])
tenure = st.sidebar.slider("Tenure (months)", 0, 72, 12)
PhoneService = st.sidebar.selectbox("Phone Service", ["Yes", "No"])
MultipleLines = st.sidebar.selectbox("Multiple Lines", ["Yes", "No", "No phone service"])
InternetService = st.sidebar.selectbox("Internet Service", ["DSL", "Fiber optic", "No"])
OnlineSecurity = st.sidebar.selectbox("Online Security", ["Yes", "No", "No internet service"])
OnlineBackup = st.sidebar.selectbox("Online Backup", ["Yes", "No", "No internet service"])
DeviceProtection = st.sidebar.selectbox("Device Protection", ["Yes", "No", "No internet service"])
TechSupport = st.sidebar.selectbox("Tech Support", ["Yes", "No", "No internet service"])
StreamingTV = st.sidebar.selectbox("Streaming TV", ["Yes", "No", "No internet service"])
StreamingMovies = st.sidebar.selectbox("Streaming Movies", ["Yes", "No", "No internet service"])
Contract = st.sidebar.selectbox("Contract", ["Month-to-month", "One year", "Two year"])
PaperlessBilling = st.sidebar.selectbox("Paperless Billing", ["Yes", "No"])
PaymentMethod = st.sidebar.selectbox("Payment Method", [
    "Electronic check",
    "Mailed check",
    "Bank transfer (automatic)",
    "Credit card (automatic)"
])
MonthlyCharges = st.sidebar.number_input("Monthly Charges", 0.0, 150.0, 50.0)
TotalCharges = st.sidebar.number_input("Total Charges", 0.0, 10000.0, tenure * MonthlyCharges)

customer_data = {
    "customerID": customerID,
    "gender": gender,
    "SeniorCitizen": SeniorCitizen,
    "Partner": Partner,
    "Dependents": Dependents,
    "tenure": tenure,
    "PhoneService": PhoneService,
    "MultipleLines": MultipleLines,
    "InternetService": InternetService,
    "OnlineSecurity": OnlineSecurity,
    "OnlineBackup": OnlineBackup,
    "DeviceProtection": DeviceProtection,
    "TechSupport": TechSupport,
    "StreamingTV": StreamingTV,
    "StreamingMovies": StreamingMovies,
    "Contract": Contract,
    "PaperlessBilling": PaperlessBilling,
    "PaymentMethod": PaymentMethod,
    "MonthlyCharges": MonthlyCharges,
    "TotalCharges": TotalCharges,
}

# Show sample high-risk customer as reference
with st.expander("📋 Load Sample High-Risk Customer"):
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
        "TotalCharges": 190.0
    }
    st.json(sample_customer, expanded=False)
    if st.button("Use Sample Customer"):
        # This would need session state to work properly; just show the data
        st.info("Copy the values above into the sidebar form.")

if st.button("Generate Recommendations", type="primary"):
    with st.spinner("Analyzing customer profile..."):
        try:
            result = get_retention_recommendation(customer_data)

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Risk Segment", result["risk_segment"])
            with col2:
                st.metric("Annual Revenue Exposure", f"${result['annual_revenue_exposure']:,.2f}")

            st.subheader("Recommended Actions")
            for rec in result["recommendations"]:
                with st.container():
                    st.info(f"**Action:** {rec['action']}\n\n**Reason:** {rec['reason']}")

        except Exception as e:
            st.error(f"Error fetching recommendations: {e}")
