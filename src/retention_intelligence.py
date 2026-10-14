from typing import Any, Dict, List


def segment_risk(probability: float) -> str:
    """
    Segments a customer into risk bands based on their churn probability.
    """
    if probability < 0.3:
        return "Low"
    elif probability < 0.65:
        return "Medium"
    else:
        return "High"

def estimate_revenue_exposure(probability: float, monthly_charges: float, expected_months: int = 12) -> float:
    """
    Estimates the potential revenue lost.
    Formula: Probability of Churn * Monthly Charges * Expected Remaining Months (default 12 for annual value)
    """
    if monthly_charges < 0 or probability < 0 or probability > 1:
        raise ValueError("Invalid probability or monthly charges.")

    return float(probability * monthly_charges * expected_months)

def generate_retention_recommendations(
    customer_data: Dict[str, Any],
    churn_probability: float,
    explanation_features: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """
    Generates rule-based retention recommendations.
    Uses the customer's raw data and their top SHAP feature contributions.
    """
    recommendations = []

    # Only generate active retention recommendations if they are Medium or High risk
    risk = segment_risk(churn_probability)
    if risk == "Low":
        recommendations.append({
            "action": "Maintain Relationship",
            "reason": "Customer is at low risk of churning."
        })
        return recommendations

    # Check contract status from raw data
    contract = customer_data.get('Contract', 'Unknown')
    if contract == 'Month-to-month':
        recommendations.append({
            "action": "Offer Annual Upgrade Discount",
            "reason": "Customer is on Month-to-month contract. Locking them into an annual contract reduces churn risk significantly."
        })

    # Check top SHAP features that are pushing churn up (positive contribution)
    positive_drivers = [feat['name'] for feat in explanation_features if feat['contribution'] > 0][:3]

    # If High Monthly Charges is a major driver of their churn probability
    if any('MonthlyCharges' in driver for driver in positive_drivers):
        recommendations.append({
            "action": "Offer $10 Monthly Loyalty Credit",
            "reason": "High monthly charges are a primary driver of this customer's churn risk."
        })

    # If Tech Support or Internet Service issues are driving it
    internet = customer_data.get('InternetService', 'Unknown')
    tech_support = customer_data.get('TechSupport', 'Unknown')

    if internet == 'Fiber optic' and tech_support == 'No':
         recommendations.append({
            "action": "Offer Free Tech Support Add-on for 3 months",
            "reason": "Customer has premium Fiber Optic but no Tech Support. Proactive support reduces churn for high-value internet users."
        })

    # Fallback if no specific rules hit for high risk
    if risk == "High" and len(recommendations) == 0:
         recommendations.append({
            "action": "Trigger Personal Agent Call",
            "reason": "Customer is at high risk of churning for unclassified reasons. Requires human intervention."
        })

    return recommendations
