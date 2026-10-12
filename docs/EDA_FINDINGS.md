# Exploratory Data Analysis (EDA) Findings

This document summarizes the insights gathered from the IBM Telco Customer Churn dataset located at `/tmp/Telco-Customer-Churn.csv`.

## 1. Class Imbalance
The target variable `Churn` is imbalanced, which is typical for churn datasets:
*   **No Churn (Retained):** ~73.46%
*   **Yes (Churned):** ~26.54%

*Implication for ML:* We must use stratified sampling for train/test splits and cross-validation to maintain this ratio. Evaluation metrics should focus on ROC-AUC, PR-AUC, Precision, Recall, and F1-score rather than simple accuracy.

## 2. Numeric Features
There are four numeric features:
*   `SeniorCitizen` (0 or 1): Technically categorical, but encoded as an integer.
*   `tenure`: Ranges from 0 to 72 months. Mean is ~32.4 months.
*   `MonthlyCharges`: Ranges from \$18.25 to \$118.75.
*   `TotalCharges`: Ranges from \$18.80 to \$8684.80.

*Data Quality Issue:* `TotalCharges` contains 11 missing values. In the raw CSV, these are represented as empty spaces `" "`. These correspond to customers with `tenure == 0` (brand new customers who haven't been billed yet).
*Resolution strategy:* During preprocessing, we will coerce these empty strings to `NaN` and impute them (e.g., filling with `0` or `MonthlyCharges`).

## 3. Categorical Features
Excluding `customerID`, there are 16 categorical features:
*   **Binary:** `gender`, `Partner`, `Dependents`, `PhoneService`, `PaperlessBilling`.
*   **Ternary (3 categories):** `MultipleLines`, `InternetService`, `OnlineSecurity`, `OnlineBackup`, `DeviceProtection`, `TechSupport`, `StreamingTV`, `StreamingMovies`, `Contract`.
*   **Quaternary (4 categories):** `PaymentMethod`.

*Observation:* Features like `OnlineSecurity` contain values "Yes", "No", and "No internet service". This introduces some collinearity with `InternetService`, which is expected but should be handled smoothly by tree-based models.

## 4. Leakage Risks
*   **customerID:** Must be dropped before model training as it has 100% cardinality and holds no predictive value, representing a leakage/overfitting risk.
*   **TotalCharges vs. MonthlyCharges & Tenure:** `TotalCharges` is highly correlated with `tenure * MonthlyCharges`. While not strict target leakage, it represents multicollinearity. We will retain it for now but note it for model explainability (SHAP).

## Conclusion
The data is relatively clean. The primary preprocessing tasks for Milestone 4 will be handling the 11 missing values in `TotalCharges`, converting target labels to binary (0/1), one-hot encoding nominal categorical variables, scaling numeric features for Logistic Regression, and dropping `customerID`.
