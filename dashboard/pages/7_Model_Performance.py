
import streamlit as st

from dashboard.api_client import get_health, get_model_info

st.set_page_config(page_title="Model Performance", page_icon="⚙️", layout="wide")
st.title("Model Performance & Diagnostics")

if not get_health():
    st.error("API is Offline.")
    st.stop()

st.subheader("Live API Metadata")
try:
    info = get_model_info()
    st.write(f"**Version:** {info['version']}")
    st.write(f"**Active Operating Threshold:** {info['threshold']}")
except Exception as e:
    st.error(f"Could not load metadata: {e}")

st.markdown("---")
st.subheader("Latest Validation Metrics (Test Set)")
metrics = {
  "precision": 0.503,
  "recall": 0.783,
  "f1": 0.613,
  "roc_auc": 0.841,
  "pr_auc": 0.632
}

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("ROC-AUC", metrics["roc_auc"])
col2.metric("PR-AUC", metrics["pr_auc"])
col3.metric("F1 Score", metrics["f1"])
col4.metric("Recall", metrics["recall"])
col5.metric("Precision", metrics["precision"])

st.markdown("""
### Note on Threshold
The model operates at a custom threshold (0.65) designed to suppress false positives and increase Precision above the baseline 0.503 reported in testing at threshold 0.5.
""")
