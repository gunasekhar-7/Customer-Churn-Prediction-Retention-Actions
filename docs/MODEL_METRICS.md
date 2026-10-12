# Model Evaluation Metrics

This document summarizes the performance of various models trained on the IBM Telco Customer Churn dataset.

## Setup
*   **Data Split:** 80% Train, 20% Test (Stratified)
*   **Preprocessing:** Median Imputation, Standard Scaling, One-Hot Encoding
*   **Target:** `Churn` (Yes=1, No=0). Baseline churn rate is ~26.5%

## Baseline & Model Comparison (Test Set)

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
