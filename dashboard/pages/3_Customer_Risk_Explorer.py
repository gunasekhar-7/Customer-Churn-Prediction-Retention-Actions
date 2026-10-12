import pandas as pd
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

                results_df = pd.DataFrame(preds)
                st.dataframe(results_df)

                st.download_button(
                    label="Download Predictions",
                    data=results_df.to_csv(index=False).encode('utf-8'),
                    file_name='predictions.csv',
                    mime='text/csv',
                )
            except Exception as e:
                st.error(f"Error scoring batch: {e}")
