import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.api_client import get_health, predict_batch

st.set_page_config(page_title="Customer Risk Explorer", page_icon="👥", layout="wide")
st.title("Customer Risk Explorer")

if not get_health():
    st.error("API is Offline.")
    st.stop()

st.write("Upload a CSV of customers to score them in batch.")
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    # clean it up just in case
    df['TotalCharges'] = df['TotalCharges'].astype(str)

    if st.button("Score Customers"):
        with st.spinner("Scoring..."):
            records = df.to_dict(orient="records")
            try:
                result = predict_batch(records)
                preds = result.get("predictions", [])

                if not preds:
                    st.warning("No predictions returned.")
                    st.stop()

                results_df = pd.DataFrame(preds)

                # Summary metrics
                total = len(results_df)
                high_risk = len(results_df[results_df['risk_segment'] == 'High Risk'])
                medium_risk = len(results_df[results_df['risk_segment'] == 'Medium Risk'])
                low_risk = len(results_df[results_df['risk_segment'] == 'Low Risk'])
                avg_prob = results_df['churn_probability'].mean()

                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("Total Scored", total)
                col2.metric("High Risk", high_risk, delta_color="inverse")
                col3.metric("Medium Risk", medium_risk)
                col4.metric("Low Risk", low_risk)
                col5.metric("Avg Churn Probability", f"{avg_prob:.1%}")

                # Risk distribution chart
                risk_counts = results_df['risk_segment'].value_counts()
                fig = px.bar(
                    x=risk_counts.index,
                    y=risk_counts.values,
                    labels={'x': 'Risk Segment', 'y': 'Count'},
                    color=risk_counts.index,
                    color_discrete_map={'Low Risk': 'green', 'Medium Risk': 'orange', 'High Risk': 'red'}
                )
                st.plotly_chart(fig, use_container_width=True)

                st.dataframe(results_df, use_container_width=True)

                st.download_button(
                    label="Download Predictions",
                    data=results_df.to_csv(index=False).encode('utf-8'),
                    file_name='predictions.csv',
                    mime='text/csv',
                )
            except Exception as e:
                st.error(f"Error scoring batch: {e}")
