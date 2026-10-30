import plotly.express as px
import streamlit as st

from dashboard.api_client import get_dashboard_metrics, get_health

st.set_page_config(page_title="Revenue Exposure", page_icon="💰", layout="wide")
st.title("Revenue Exposure Dashboard")

if not get_health():
    st.error("API is Offline.")
    st.stop()

try:
    metrics = get_dashboard_metrics()
except Exception as e:
    st.error(f"Failed to fetch metrics: {e}")
    st.stop()

# Summary metrics
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Active Customers", f"{metrics['total_customers']:,}")
with col2:
    st.metric("High Risk Customers", f"{metrics['high_risk_customers']:,}")
with col3:
    st.metric("Medium Risk Customers", f"{metrics['medium_risk_customers']:,}")
with col4:
    st.metric("Annual Revenue at Risk", f"${metrics['annual_revenue_at_risk']:,.0f}")

st.markdown("---")

# Risk distribution chart
st.subheader("Customer Risk Distribution")
risk_dist = metrics['risk_distribution']
if risk_dist:
    fig = px.pie(
        values=list(risk_dist.values()),
        names=list(risk_dist.keys()),
        color=list(risk_dist.keys()),
        color_discrete_map={'Low Risk': 'green', 'Medium Risk': 'orange', 'High Risk': 'red'},
        hole=0.4
    )
    fig.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig, use_container_width=True)

# Revenue exposure breakdown
st.subheader("Revenue Exposure Breakdown")
st.markdown(f"""
**Annual Revenue at Risk:** ${metrics['annual_revenue_at_risk']:,.0f}

**By Risk Segment:**
- **High Risk:** {metrics['high_risk_customers']:,} customers
- **Medium Risk:** {metrics['medium_risk_customers']:,} customers
- **Low Risk:** {metrics['low_risk_customers']:,} customers
""")

# Retention ROI projection
st.subheader("Retention ROI Projection")
st.markdown("""
*Assumptions: 10% intervention success rate on High/Medium risk, $10 credit cost per intervention*

| Segment | Customers | Avg Monthly Charges | Annual Exposure | Interventions | Cost | Expected Saved | Net ROI |
|---------|-----------|---------------------|-----------------|---------------|------|----------------|---------|
| High Risk | {:,} | ${:,.0f} | ${:,.0f} | {:,} | ${:,.0f} | ${:,.0f} | +{:,.0f}% |
| Medium Risk | {:,} | ${:,.0f} | ${:,.0f} | {:,} | ${:,.0f} | ${:,.0f} | +{:,.0f}% |
""".format(
    metrics['high_risk_customers'],
    metrics['annual_revenue_at_risk'] / max(metrics['high_risk_customers'] + metrics['medium_risk_customers'], 1) / 12 * 12,
    metrics['annual_revenue_at_risk'] * metrics['high_risk_customers'] / max(metrics['high_risk_customers'] + metrics['medium_risk_customers'], 1),
    metrics['high_risk_customers'],
    metrics['high_risk_customers'] * 10,
    metrics['annual_revenue_at_risk'] * metrics['high_risk_customers'] / max(metrics['high_risk_customers'] + metrics['medium_risk_customers'], 1) * 0.1,
    (metrics['annual_revenue_at_risk'] * metrics['high_risk_customers'] / max(metrics['high_risk_customers'] + metrics['medium_risk_customers'], 1) * 0.1 - metrics['high_risk_customers'] * 10) / max(metrics['high_risk_customers'] * 10, 1) * 100,
    metrics['medium_risk_customers'],
    metrics['annual_revenue_at_risk'] / max(metrics['high_risk_customers'] + metrics['medium_risk_customers'], 1) / 12 * 12,
    metrics['annual_revenue_at_risk'] * metrics['medium_risk_customers'] / max(metrics['high_risk_customers'] + metrics['medium_risk_customers'], 1),
    metrics['medium_risk_customers'],
    metrics['medium_risk_customers'] * 10,
    metrics['annual_revenue_at_risk'] * metrics['medium_risk_customers'] / max(metrics['high_risk_customers'] + metrics['medium_risk_customers'], 1) * 0.1,
    (metrics['annual_revenue_at_risk'] * metrics['medium_risk_customers'] / max(metrics['high_risk_customers'] + metrics['medium_risk_customers'], 1) * 0.1 - metrics['medium_risk_customers'] * 10) / max(metrics['medium_risk_customers'] * 10, 1) * 100,
))
