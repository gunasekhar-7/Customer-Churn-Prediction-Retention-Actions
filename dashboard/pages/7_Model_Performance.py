
import streamlit as st

from dashboard.api_client import get_health, get_model_info, get_model_metrics

st.set_page_config(page_title="Model Performance", page_icon="⚙️", layout="wide")
st.title("Model Performance & Diagnostics")

if not get_health():
    st.error("API is Offline.")
    st.stop()

st.subheader("Live API Metadata")
try:
    info = get_model_info()
    st.write(f"**Version:** {info['version']}")
    st.write(f"**Active Operating Threshold:** {info['threshold']:.4f}")
except Exception as e:
    st.error(f"Could not load metadata: {e}")

st.markdown("---")

# Fetch real model metrics from artifact
st.subheader("Model Performance Metrics (Held-Out Test Set)")
try:
    metrics = get_model_metrics()
    test_metrics = metrics.get("test_metrics", {})
    threshold_meta = metrics.get("threshold_metadata", {})

    if test_metrics:
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("ROC-AUC", f"{test_metrics.get('roc_auc', 0):.3f}")
        col2.metric("PR-AUC", f"{test_metrics.get('pr_auc', 0):.3f}")
        col3.metric("F1 Score", f"{test_metrics.get('f1', 0):.3f}")
        col4.metric("Recall", f"{test_metrics.get('recall', 0):.3f}")
        col5.metric("Precision", f"{test_metrics.get('precision', 0):.3f}")

        st.markdown("---")

        st.subheader("Threshold Selection Details")
        col1, col2, col3 = st.columns(3)
        col1.metric("Selection Rule", threshold_meta.get("selection_rule", "N/A"))
        col2.metric("Min Recall Requirement", f"{threshold_meta.get('min_recall_requirement', 0):.0%}")
        col3.metric("Fallback Used", "Yes" if threshold_meta.get("fallback_used") else "No")

        col1, col2, col3 = st.columns(3)
        col1.metric("Selected Precision", f"{threshold_meta.get('selected_precision', 0):.3f}")
        col2.metric("Selected Recall", f"{threshold_meta.get('selected_recall', 0):.3f}")
        col3.metric("Selected F1", f"{threshold_meta.get('selected_f1', 0):.3f}")

        # Confusion matrix if available
        cm = test_metrics.get("confusion_matrix")
        if cm:
            st.markdown("---")
            st.subheader("Confusion Matrix (Test Set)")
            cm_df = st.dataframe(
                [[cm[0][0], cm[0][1], "True Neg", "False Pos"],
                 [cm[1][0], cm[1][1], "False Neg", "True Pos"]],
                columns=["Predicted 0", "Predicted 1", "Actual 0", "Actual 1"]
            )
    else:
        st.warning("No test metrics available in artifact metadata.")

except Exception as e:
    st.error(f"Could not load model metrics: {e}")

# Data provenance
st.markdown("---")
st.subheader("Data Provenance")
try:
    metrics = get_model_metrics()
    provenance = metrics.get("data_provenance", {})
    if provenance:
        st.write(f"**Dataset:** {provenance.get('dataset', 'Unknown')}")
        st.write(f"**SHA-256:** {provenance.get('sha256', 'N/A')[:16]}...")
        st.write(f"**Source:** {provenance.get('source_url', 'Unknown')}")
        st.write(f"**License:** {provenance.get('license', 'Unknown')}")
        st.write(f"**Rows:** {provenance.get('num_rows', 'Unknown'):,}")
except Exception as e:
    st.warning(f"Could not load provenance: {e}")
