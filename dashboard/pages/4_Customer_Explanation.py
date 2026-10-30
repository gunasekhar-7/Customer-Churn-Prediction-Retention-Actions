import plotly.graph_objects as go
import streamlit as st

from dashboard.api_client import explain, get_health

st.set_page_config(page_title="Customer Explanation", page_icon="🧠", layout="wide")
st.title("Customer Explanation (SHAP)")

if not get_health():
    st.error("API is Offline.")
    st.stop()

st.sidebar.header("Customer Input")

# All required fields per TelcoCustomerFeatures schema
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

st.info("Input customer attributes on the left to see what drives their specific churn probability.")

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

if st.button("Generate Explanation"):
    with st.spinner("Calculating SHAP values..."):
        try:
            result = explain(customer_data)

            st.metric("Base Expected Value (Log Odds)", f"{result['base_value']:.4f}")

            features = result['features'][:15]  # Top 15
            names = [f['name'] for f in features]
            contributions = [f['contribution'] for f in features]
            colors = ['red' if c > 0 else 'green' for c in contributions]

            fig = go.Figure(go.Bar(
                x=contributions,
                y=names,
                orientation='h',
                marker_color=colors
            ))
            fig.update_layout(
                title="Top Features Driving Churn (Red = Increases Risk, Green = Decreases Risk)",
                yaxis={'categoryorder': 'total ascending'},
                height=600
            )
            st.plotly_chart(fig, use_container_width=True)

            # Show prediction probability
            prob = 1 / (1 + pow(2.718, -result['base_value'] - sum(contributions)))
            st.metric("Estimated Churn Probability", f"{prob:.2%}")

        except Exception as e:
            st.error(f"Error fetching explanation: {e}")
