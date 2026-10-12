# Model Selection and Explainability (SHAP)

## 1. Model Selection
Based on the results from Milestone 5, we are selecting **Logistic Regression (with balanced class weights)** as the primary model.
- **Reasoning:** It achieved the highest ROC-AUC score (0.841) out-of-the-box compared to Random Forest and XGBoost. It also natively outputs clear probabilities which are exceptionally cheap and fast to explain via `shap.LinearExplainer`.

## 2. Threshold Engineering
By default, `predict()` uses a 0.5 probability cutoff. Our tests show that bumping this threshold up to **0.65** decreases the sheer volume of positive churn predictions from 582 to 440 (on a ~1400 customer test set).
- **Impact:** Higher thresholds increase Precision (fewer false positives) but lower Recall (we miss some actual churners).
- **Implementation:** The `predict_with_threshold()` function allows the business logic layer to dynamically set this based on ROI (e.g. if sending a retention discount costs $10, we want high precision to not waste money. If an email costs $0.01, we want high recall at threshold 0.3 to cast a wide net).

## 3. Global Explainability (SHAP)
Taking the mean absolute SHAP values across the training data reveals the primary drivers of churn globally for this model:
1.  **`tenure` (0.9352):** The strongest predictor. Customers who have been with Telco longer are significantly less likely to churn.
2.  **`MonthlyCharges` (0.5517):** High monthly bills correlate with a higher probability of churning.
3.  **`InternetService_Fiber optic` (0.3549):** Having Fiber Optic internet is strongly tied to churn.
4.  **`TotalCharges` (0.3529):** Cumulative spend over the lifetime.
5.  **`Contract_Month-to-month` (0.3149):** Customers not locked into 1- or 2-year contracts are high flight risks.

## 4. Local Explainability (SHAP)
For a specific customer (e.g., the first test customer), we see the individual pushes and pulls:
- **Base Value:** -0.5734 (the average log-odds prediction across the dataset).
- **tenure (-1.9403):** This customer has high tenure, massively pulling their churn probability DOWN (negative log-odds).
- **TotalCharges (+1.3143):** Their cumulative charges push their churn risk back UP.
- **Contract_Two year (-0.5919):** Because they are on a two-year contract, their risk is pulled DOWN.
- This creates an interpretable, additive explanation that we will surface in the Streamlit UI.
