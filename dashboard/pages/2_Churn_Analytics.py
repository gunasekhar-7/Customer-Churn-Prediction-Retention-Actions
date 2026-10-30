from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Churn Analytics", page_icon="🔍", layout="wide")
st.title("Historical Churn Analytics")

@st.cache_data
def load_data():
    # Try project-relative path first, then fallback
    for path in [
        Path(__file__).parent.parent.parent / "data" / "Telco-Customer-Churn.csv",
        Path("/tmp/Telco-Customer-Churn.csv"),
    ]:
        try:
            return pd.read_csv(path)
        except Exception:
            continue
    return pd.DataFrame()

df = load_data()

if df.empty:
    st.error("Historical dataset not found. Expected at data/Telco-Customer-Churn.csv")
else:
    st.subheader("Churn by Contract Type")
    fig1 = px.histogram(df, x="Contract", color="Churn", barmode="group")
    st.plotly_chart(fig1, use_container_width=True)

    st.subheader("Tenure Distribution by Churn Status")
    fig2 = px.box(df, x="Churn", y="tenure", color="Churn")
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Monthly Charges by Churn Status")
    fig3 = px.box(df, x="Churn", y="MonthlyCharges", color="Churn")
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Churn Rate by Internet Service")
    churn_by_internet = df.groupby("InternetService")["Churn"].apply(lambda x: (x == "Yes").mean()).reset_index()
    churn_by_internet.columns = ["InternetService", "ChurnRate"]
    fig4 = px.bar(churn_by_internet, x="InternetService", y="ChurnRate", text_auto=".1%")
    st.plotly_chart(fig4, use_container_width=True)
