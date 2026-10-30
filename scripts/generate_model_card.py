#!/usr/bin/env python
"""
Generate Model Card from trained model artifact metadata.

Reads the serialized model artifact and produces a structured MODEL_CARD.md
following the Google Model Card format (adapted for this project).

Usage:
    python scripts/generate_model_card.py
    python scripts/generate_model_card.py --artifact models/model_v1.joblib --output docs/MODEL_CARD.md
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, cast

import joblib

DEFAULT_ARTIFACT_PATH = Path(__file__).parent.parent / "models" / "model_v1.joblib"
DEFAULT_OUTPUT_PATH = Path(__file__).parent.parent / "docs" / "MODEL_CARD.md"


def load_artifact(artifact_path: Path) -> Dict[str, Any]:
    """Load model artifact from disk."""
    if not artifact_path.exists():
        raise FileNotFoundError(f"Artifact not found at {artifact_path}")
    return cast(Dict[str, Any], joblib.load(artifact_path))


def format_metrics(metrics: Dict[str, Any]) -> str:
    """Format metrics dictionary as markdown table."""
    if not metrics:
        return "No metrics available."

    rows = []
    for key, value in metrics.items():
        if isinstance(value, float):
            rows.append(f"| {key.replace('_', ' ').title()} | {value:.4f} |")
        elif isinstance(value, list):
            rows.append(f"| {key.replace('_', ' ').title()} | `{json.dumps(value)}` |")
        else:
            rows.append(f"| {key.replace('_', ' ').title()} | {value} |")

    return (
        "| Metric | Value |\n"
        "|--------|-------|\n"
        + "\n".join(rows)
    )


def format_confusion_matrix(cm: list) -> str:
    """Format confusion matrix as markdown table."""
    if not cm or len(cm) != 2:
        return "Not available"

    return (
        "| | Predicted 0 (No Churn) | Predicted 1 (Churn) |\n"
        "|---|---|---|\n"
        f"| **Actual 0 (No Churn)** | {cm[0][0]} (TN) | {cm[0][1]} (FP) |\n"
        f"| **Actual 1 (Churn)** | {cm[1][0]} (FN) | {cm[1][1]} (TP) |"
    )


def format_provenance(provenance: Dict[str, Any]) -> str:
    """Format data provenance as markdown."""
    if not provenance:
        return "Not available"

    lines = []
    for key, value in provenance.items():
        if key == "target_distribution" and isinstance(value, dict):
            lines.append(f"**{key.replace('_', ' ').title()}**:")
            for k, v in value.items():
                lines.append(f"  - {k}: {v}")
        elif value:
            lines.append(f"**{key.replace('_', ' ').title()}**: {value}")

    return "\n".join(lines) if lines else "Not available"


def format_threshold_metadata(threshold_meta: Dict[str, Any]) -> str:
    """Format threshold selection metadata."""
    if not threshold_meta:
        return "Not available"

    lines = []
    for key, value in threshold_meta.items():
        if key == "threshold_candidates":
            continue  # Skip detailed candidates for brevity
        if isinstance(value, float):
            lines.append(f"- **{key.replace('_', ' ').title()}**: {value:.4f}")
        elif isinstance(value, bool):
            lines.append(f"- **{key.replace('_', ' ').title()}**: {'Yes' if value else 'No'}")
        else:
            lines.append(f"- **{key.replace('_', ' ').title()}**: {value}")

    return "\n".join(lines) if lines else "Not available"


def generate_model_card(artifact: Dict[str, Any]) -> str:
    """Generate model card markdown from artifact."""
    metadata = artifact.get("metadata", {})

    # Extract sections
    version = metadata.get("version", "Unknown")
    threshold = metadata.get("threshold", "Unknown")
    timestamp = metadata.get("timestamp", "Unknown")
    test_metrics = metadata.get("test_metrics", {})
    threshold_metadata = metadata.get("threshold_metadata", {})
    data_provenance = metadata.get("data_provenance", {})
    training_config = metadata.get("training_config", {})
    reference_predictions = metadata.get("reference_predictions", [])
    shap_background = metadata.get("shap_background", [])
    artifact_sha256 = metadata.get("artifact_sha256", "Unknown")

    # Model details
    model_type = training_config.get("model_type", "LogisticRegression")
    class_weight = training_config.get("class_weight", "balanced")
    max_iter = training_config.get("max_iter", 1000)
    random_state = training_config.get("random_state", 42)
    train_samples = training_config.get("train_samples", "Unknown")
    val_samples = training_config.get("val_samples", "Unknown")
    test_samples = training_config.get("test_samples", "Unknown")
    min_recall_req = training_config.get("min_recall_requirement", 0.70)

    # Quality gate
    quality_gate_passed = test_metrics.get("roc_auc", 0) >= 0.80

    card = f"""# Model Card: Customer Churn Prediction

> **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
> **Artifact SHA-256**: `{artifact_sha256}`  
> **Version**: {version}

---

## 📋 Model Details

| Property | Value |
|----------|-------|
| **Model Name** | Customer Churn Prediction |
| **Version** | {version} |
| **Model Type** | {model_type} |
| **Framework** | scikit-learn |
| **Task** | Binary Classification (Churn: Yes/No) |
| **Threshold** | {threshold:.4f} |
| **Training Date** | {timestamp} |
| **Artifact SHA-256** | `{artifact_sha256}` |

---

## 🎯 Intended Use

**Primary Use Case**: Predict customer churn probability for telecommunications customers to enable proactive retention interventions.

**Intended Users**:
- Data Science Team (model monitoring, retraining)
- Customer Success Team (prioritize outreach)
- Marketing Team (targeted retention campaigns)
- Business Analysts (revenue exposure analysis)

**Out of Scope**:
- Real-time fraud detection
- Credit risk scoring
- Any regulated decision-making without human review

---

## 📊 Training Data

### Dataset
{format_provenance(data_provenance)}

### Split
- **Train**: {train_samples:,} samples (60%)
- **Validation**: {val_samples:,} samples (20%) — *used for threshold selection*
- **Test**: {test_samples:,} samples (20%) — *held-out, never used for tuning*

### Preprocessing
- Categorical features: One-hot encoded
- Numerical features: Standardized
- Target: Binary (Churn: Yes=1, No=0)
- Class imbalance handled via `class_weight='balanced'`

---

## ⚙️ Model Configuration

| Parameter | Value |
|-----------|-------|
| **Algorithm** | {model_type} |
| **Class Weight** | {class_weight} |
| **Max Iterations** | {max_iter} |
| **Random State** | {random_state} |
| **Min Recall Requirement** | {min_recall_req:.0%} |

---

## 📈 Threshold Selection

**Rule**: Highest precision at recall ≥ {min_recall_req:.0%} (on validation set)

{format_threshold_metadata(threshold_metadata)}

**Fallback**: Best F1 score if no threshold meets recall requirement.

---

## 📏 Evaluation Metrics (Held-Out Test Set)

{format_metrics(test_metrics)}

### Confusion Matrix
{format_confusion_matrix(test_metrics.get('confusion_matrix', []))}

### Quality Gate
| Gate | Threshold | Result | Status |
|------|-----------|--------|--------|
| ROC-AUC | ≥ 0.80 | {test_metrics.get('roc_auc', 0):.4f} | {'✅ PASSED' if quality_gate_passed else '❌ FAILED'} |

---

## 🔍 Explainability

- **Method**: SHAP (LinearExplainer for Logistic Regression)
- **Background Sample**: {len(shap_background)} rows from validation set
- **Reference Predictions**: {len(reference_predictions)} validation predictions for drift monitoring
- **Global Feature Importance**: Available via `/explain` endpoint
- **Local Explanations**: Per-customer SHAP values with base value

---

## 📉 Drift Monitoring

- **Method**: Population Stability Index (PSI) + Kolmogorov-Smirnov (KS) test
- **Reference Distribution**: {len(reference_predictions)} validation predictions
- **Window**: Rolling 1,000 predictions
- **Evaluation Interval**: 5 minutes
- **Alert Thresholds**:
  - PSI > 0.10 → Drift Alert
  - PSI > 0.05 → Warning
  - KS p-value < 0.05 → Drift Alert

---

## 🔒 Data Protection & Privacy

- **Data Minimization**: Only essential fields stored in prediction records (customerID hashed, MonthlyCharges, tenure, Contract)
- **PII Handling**: Customer IDs hashed with salt (SHA-256) before storage
- **Retention**: 90 days default (configurable via `DATA_RETENTION_DAYS`)
- **Compliance**: GDPR/CCPA aligned by design

---

## ⚠️ Limitations

1. **Dataset Size**: Training on ~100 samples (Telco dataset subset); production should use full dataset (7,043 rows)
2. **Class Imbalance**: Churn rate ~26%; balanced class weight mitigates but precision at high recall is moderate (~0.45)
3. **Feature Interactions**: Linear model cannot capture complex non-linear interactions
3. **Temporal Drift**: Customer behavior evolves; requires periodic retraining (recommended quarterly)
4. **No Ground Truth Monitoring**: Drift detection uses prediction scores only; label feedback loop needed for true performance tracking
5. **Single Model**: No ensemble or A/B testing framework

---

## 🔄 Model Lifecycle

| Stage | Frequency | Trigger |
|-------|-----------|---------|
| **Retraining** | Quarterly | Scheduled or drift alert |
| **Validation** | Per retrain | Held-out test set (ROC-AUC ≥ 0.80) |
| **Deployment** | Per retrain | Blue/green via ECS/Fargate |
| **Monitoring** | Continuous | PSI/KS every 5 min |

---

## 📚 References

- **Data Provenance**: [docs/DATA_PROVENANCE.md](../DATA_PROVENANCE.md)
- **Architecture**: [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
- **Business Rules**: [docs/BUSINESS_RULES.md](../BUSINESS_RULES.md)
- **MLOps & Monitoring**: [docs/MLOPS_AND_MONITORING.md](../MLOPS_AND_MONITORING.md)
- **Model Selection & SHAP**: [docs/MODEL_SELECTION_AND_SHAP.md](../MODEL_SELECTION_AND_SHAP.md)
- **Model Metrics**: [docs/MODEL_METRICS.md](../MODEL_METRICS.md)

---

## 📝 Changelog

| Version | Date | Changes |
|---------|------|---------|
| {version} | {timestamp[:10]} | Initial release |

---

*This model card was auto-generated from artifact metadata. Do not edit manually — regenerate using `scripts/generate_model_card.py`.*
"""
    return card


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Model Card from model artifact metadata",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=DEFAULT_ARTIFACT_PATH,
        help="Path to model artifact (.joblib)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output path for MODEL_CARD.md"
    )
    args = parser.parse_args()

    print(f"Loading artifact from {args.artifact}...")
    artifact = load_artifact(args.artifact)

    print("Generating model card...")
    card = generate_model_card(artifact)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(card, encoding="utf-8")
    print(f"Model card written to {args.output}")


if __name__ == "__main__":
    main()
