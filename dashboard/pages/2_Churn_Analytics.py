import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Churn Analytics", page_icon="🔍", layout="wide")
st.title("Historical Churn Analytics")

@st.cache_data
def load_data():
    try:
        return pd.read_csv('/tmp/Telco-Customer-Churn.csv')
    except Exception:
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.error("Historical dataset not found at /tmp/Telco-Customer-Churn.csv")
else:
    st.subheader("Churn by Contract Type")
    fig1 = px.histogram(df, x="Contract", color="Churn", barmode="group")
    st.plotly_chart(fig1, use_container_width=True)

    st.subheader("Tenure Distribution by Churn Status")
    fig2 = px.box(df, x="Churn", y="tenure", color="Churn")
    st.plotly_chart(fig2, use_container_width=True)
