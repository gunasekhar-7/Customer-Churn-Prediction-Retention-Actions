# Model Card: Customer Churn Prediction

> **Generated**: 2026-10-25 11:24:20  
> **Artifact SHA-256**: `91ed1cc155850b140106007256cf175b1aeb3fe8ffaca3227ad8718d023f20ad`  
> **Version**: 1.0.0

---

## 📋 Model Details

| Property | Value |
|----------|-------|
| **Model Name** | Customer Churn Prediction |
| **Version** | 1.0.0 |
| **Model Type** | LogisticRegression |
| **Framework** | scikit-learn |
| **Task** | Binary Classification (Churn: Yes/No) |
| **Threshold** | 0.6478 |
| **Training Date** | 2026-10-25T11:24:10.944914 |
| **Artifact SHA-256** | `91ed1cc155850b140106007256cf175b1aeb3fe8ffaca3227ad8718d023f20ad` |

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
**File**: Telco-Customer-Churn-FULL.csv
**Sha256**: 16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91
**Num Rows**: 7043
**Target Distribution**:
  - No: 5174
  - Yes: 1869
**Source Url**: https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv
**Origin Repository**: github.com/IBM/telco-customer-churn-on-icp4d
**License**: Apache-2.0
**Dataset**: IBM Telco Customer Churn (full, 7043 rows)
**Provenance Document**: docs/DATA_PROVENANCE.md

### Split
- **Train**: 4,225 samples (60%)
- **Validation**: 1,409 samples (20%) — *used for threshold selection*
- **Test**: 1,409 samples (20%) — *held-out, never used for tuning*

### Preprocessing
- Categorical features: One-hot encoded
- Numerical features: Standardized
- Target: Binary (Churn: Yes=1, No=0)
- Class imbalance handled via `class_weight='balanced'`

---

## ⚙️ Model Configuration

| Parameter | Value |
|-----------|-------|
| **Algorithm** | LogisticRegression |
| **Class Weight** | balanced |
| **Max Iterations** | 1000 |
| **Random State** | 42 |
| **Min Recall Requirement** | 70% |

---

## 📈 Threshold Selection

**Rule**: Highest precision at recall ≥ 70% (on validation set)

- **Selection Rule**: highest_precision_at_recall_ge_0.7
- **Min Recall Requirement**: 0.7000
- **Selected Threshold**: 0.6478
- **Selected Precision**: 0.5950
- **Selected Recall**: 0.7032
- **Selected F1**: 0.6446
- **Fallback Used**: No

**Fallback**: Best F1 score if no threshold meets recall requirement.

---

## 📏 Evaluation Metrics (Held-Out Test Set)

| Metric | Value |
|--------|-------|
| Roc Auc | 0.8320 |
| Pr Auc | 0.6235 |
| Precision | 0.5588 |
| Recall | 0.6604 |
| F1 | 0.6054 |
| Confusion Matrix | `[[840, 195], [127, 247]]` |

### Confusion Matrix
| | Predicted 0 (No Churn) | Predicted 1 (Churn) |
|---|---|---|
| **Actual 0 (No Churn)** | 840 (TN) | 195 (FP) |
| **Actual 1 (Churn)** | 127 (FN) | 247 (TP) |

### Quality Gate
| Gate | Threshold | Result | Status |
|------|-----------|--------|--------|
| ROC-AUC | ≥ 0.80 | 0.8320 | ✅ PASSED |

---

## 🔍 Explainability

- **Method**: SHAP (LinearExplainer for Logistic Regression)
- **Background Sample**: 100 rows from validation set
- **Reference Predictions**: 1409 validation predictions for drift monitoring
- **Global Feature Importance**: Available via `/explain` endpoint
- **Local Explanations**: Per-customer SHAP values with base value

---

## 📉 Drift Monitoring

- **Method**: Population Stability Index (PSI) + Kolmogorov-Smirnov (KS) test
- **Reference Distribution**: 1409 validation predictions
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
| 1.0.0 | 2026-10-25 | Initial release |

---

*This model card was auto-generated from artifact metadata. Do not edit manually — regenerate using `scripts/generate_model_card.py`.*
