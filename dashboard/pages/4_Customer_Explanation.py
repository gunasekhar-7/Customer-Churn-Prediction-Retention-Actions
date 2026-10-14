import plotly.graph_objects as go
import streamlit as st

from dashboard.api_client import explain, get_health

st.set_page_config(page_title="Customer Explanation", page_icon="🧠", layout="wide")
st.title("Customer Explanation (SHAP)")

if not get_health():
    st.error("API is Offline.")
    st.stop()

st.sidebar.header("Customer Input")
# Just a small subset to test
customerID = st.sidebar.text_input("Customer ID", "TEST-1")
tenure = st.sidebar.slider("Tenure (months)", 0, 72, 12)
monthly_charges = st.sidebar.number_input("Monthly Charges", 0.0, 150.0, 50.0)
contract = st.sidebar.selectbox("Contract", ["Month-to-month", "One year", "Two year"])

st.info("Input arbitrary customer attributes on the left to see what drives their specific churn probability.")

customer_data = {
    "customerID": customerID,
    "gender": "Female",
    "SeniorCitizen": 0,
    "Partner": "Yes",
    "Dependents": "No",
    "tenure": tenure,
    "PhoneService": "Yes",
    "MultipleLines": "No",
    "InternetService": "DSL",
    "OnlineSecurity": "No",
    "OnlineBackup": "Yes",
    "DeviceProtection": "No",
    "TechSupport": "Yes",
    "StreamingTV": "No",
    "StreamingMovies": "No",
    "Contract": contract,
    "PaperlessBilling": "Yes",
    "PaymentMethod": "Electronic check",
    "MonthlyCharges": monthly_charges,
    "TotalCharges": str(tenure * monthly_charges)
}

if st.button("Generate Explanation"):
    with st.spinner("Calculating SHAP values..."):
        try:
            result = explain(customer_data)

            st.metric("Base Expected Value (Log Odds)", f"{result['base_value']:.4f}")

            features = result['features'][:10] # Top 10
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
                yaxis={'categoryorder':'total ascending'}
            )
            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Error fetching explanation: {e}")
