import plotly.express as px
import streamlit as st

from dashboard.api_client import get_dashboard_metrics, get_health

st.set_page_config(page_title="Executive Overview", page_icon="📈", layout="wide")
st.title("Executive Overview")

if not get_health():
    st.error("API is Offline.")
    st.stop()

try:
    metrics = get_dashboard_metrics()
except Exception as e:
    st.error(f"Failed to fetch metrics: {e}")
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Total Active Customers", f"{metrics['total_customers']:,}")
col2.metric("High Risk Customers", f"{metrics['high_risk_customers']:,}",
            f"{metrics['high_risk_customers']/max(metrics['total_customers'],1)*100:.1f}%",
            delta_color="inverse")
col3.metric("Annual Revenue at Risk", f"${metrics['annual_revenue_at_risk']:,.0f}")

st.markdown("### Risk Distribution")
risk_dist = metrics['risk_distribution']
if risk_dist:
    fig = px.bar(
        x=list(risk_dist.keys()),
        y=list(risk_dist.values()),
        labels={'x': 'Risk Segment', 'y': 'Number of Customers'},
        color=list(risk_dist.keys()),
        color_discrete_map={'Low Risk': 'green', 'Medium Risk': 'orange', 'High Risk': 'red'}
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No prediction data available yet. Score some customers to see risk distribution.")
