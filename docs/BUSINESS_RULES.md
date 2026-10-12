# Retention Intelligence Business Rules

This document outlines the assumptions and formulas used to translate ML probabilities into actionable business intelligence.

## 1. Customer Risk Segmentation
Customers are bucketed into risk segments based on their churn probability:
*   **Low Risk:** `< 30%` Probability. No active intervention needed; these customers are historically stable.
*   **Medium Risk:** `30% - 64%` Probability. Ripe for automated marketing interventions and discounts.
*   **High Risk:** `>= 65%` Probability. High flight risk. Requires immediate, aggressive intervention.

*(Note: The 65% threshold was determined during Milestone 6 based on optimizing model Precision).*

## 2. Revenue Exposure Estimation
We estimate "Value at Risk" rather than definitive "Realized Losses."
*   **Formula:** `Churn Probability * Monthly Charges * Expected Remaining Months`
*   **Assumption:** We default to `Expected Remaining Months = 12` to calculate *Annualized Value at Risk*.
*   **Implication:** A customer paying $100/mo with an 80% churn risk represents $960 of exposed annual revenue. Interventions costing less than this exposure yield a positive ROI.

## 3. Retention Recommendations
Recommendations are rule-based, taking into account raw customer data alongside their local SHAP explanations.

| Rule Trigger | Action | Reason |
| :--- | :--- | :--- |
| **Probability < 30%** | Maintain Relationship | Save marketing budget; customer is stable. |
| **Contract == "Month-to-month"** | Offer Annual Upgrade Discount | Locking customers into annual contracts significantly drops their baseline risk. |
| **SHAP says `MonthlyCharges` > 0** | Offer $10 Monthly Loyalty Credit | SHAP identified their specific high bill as the reason they might churn. Lower the bill slightly to retain the bulk of the revenue. |
| **Internet == "Fiber optic" AND TechSupport == "No"** | Offer Free Tech Support (3 mo) | Premium internet users who lack support churn faster. Proactive support fixes this. |
| **High Risk AND no rules apply** | Trigger Personal Agent Call | Human intervention is required when generic rules fail to map to a high-risk user. |
