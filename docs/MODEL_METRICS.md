# Model Evaluation Metrics

This document summarizes the performance of various models trained on the IBM Telco Customer Churn dataset.

## Setup
*   **Data Split:** 60% Train, 20% Validation, 20% Test (Stratified)
*   **Preprocessing:** Median Imputation, Standard Scaling, One-Hot Encoding
*   **Target:** `Churn` (Yes=1, No=0). Baseline churn rate is ~26.5%
*   **Dataset provenance:** see `docs/DATA_PROVENANCE.md` (source URL, license, SHA-256, data-quality checks)

## Shipped Production Artifact — `models/model_v1.joblib` (v1.0.0)

**Verified 2026-10-16** by running the real workflow:

```bash
python -m scripts.train_and_serialize --data-path data/Telco-Customer-Churn-FULL.csv
```

on the checksum-verified full IBM dataset (7,043 rows; SHA-256 `16320c9c…55e91`).

| Property | Actual measured value |
| :--- | :--- |
| Artifact version | **1.0.0** (production, not a test artifact) |
| Split (train/val/test) | 4,225 / 1,409 / 1,409 (stratified 60/20/20) |
| Decision threshold | **0.6478** — selected on *validation only*, rule: maximize precision subject to recall ≥ 0.70 (val precision 0.5950, val recall 0.7032) |
| **Test ROC-AUC** | **0.8320** — quality gate (≥ 0.80): **PASSED** |
| Test PR-AUC | 0.6235 |
| Test Precision | 0.5588 |
| Test Recall | 0.6604 |
| Test F1 | 0.6054 |
| Test confusion matrix | `[[840, 195], [127, 247]]` |
| Features | 46 (preprocessing fitted on train only; target excluded) |
| Drift reference | 1,409 validation-set score predictions |
| Data provenance | recorded in artifact metadata (`data_provenance` block: source URL, SHA-256, license Apache-2.0) |

The held-out test set was used only for the final evaluation; threshold selection used validation data exclusively.

## Historical Notebook Benchmarks (model-selection experiments, full dataset)

The following table records earlier notebook experiments used for model selection on the full dataset. They are **target benchmarks**, distinct from the shipped v1.0.0 artifact metrics above, and are **not reproducible with the 100-row sample dataset**.

| Model | ROC-AUC | PR-AUC | F1-Score | Precision | Recall | True Positives | False Positives |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Dummy (Prior)** | 0.500 | 0.265 | 0.000 | 0.000 | 0.000 | 0 | 0 |
| **Logistic Regression** | 0.841 | 0.632 | 0.613 | 0.503 | 0.783 | 293 | 289 |
| **Random Forest** | 0.821 | 0.602 | 0.589 | 0.556 | 0.626 | 234 | 187 |
| **XGBoost** | 0.814 | 0.611 | 0.575 | 0.516 | 0.650 | 243 | 228 |

### Notes on Class Imbalance:
To handle class imbalance:
*   Logistic Regression and Random Forest used `class_weight="balanced"`.
*   XGBoost used `scale_pos_weight = (count_negative / count_positive)`.

### Findings:
1.  **Best Overall Separator (ROC-AUC):** Logistic Regression performs surprisingly well on this dataset out of the box (`ROC-AUC = 0.841`).
2.  **Recall vs Precision Tradeoff:** Logistic Regression with balanced class weights strongly favors finding churners (`Recall = 0.783`), at the cost of high false positives (`Precision = 0.503`). This means we catch most people who will churn, but we also flag many people who won't.
3.  **Next Steps:** For Milestone 6, we will tune the threshold based on the business costs of intervention vs losing a customer, rather than strictly relying on the default 0.5 probability threshold.

## Sample Dataset Metrics (100-row sample included in repository)

The following metrics are from training on the 100-row sample dataset included in this repository. **This dataset is insufficient for production model quality and is provided only for pipeline testing.**

| Model | ROC-AUC | PR-AUC | F1-Score | Precision | Recall |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Logistic Regression (sample)** | 0.3214 | 0.2531 | 0.4000 | 0.2857 | 0.6667 |

**Quality Gate Status:** The 100-row sample **fails** the ROC-AUC ≥ 0.80 quality gate. The full IBM Telco dataset (~7,000 rows) is required to pass the quality gate and achieve production metrics.
