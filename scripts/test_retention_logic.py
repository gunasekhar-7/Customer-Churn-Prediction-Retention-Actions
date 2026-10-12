import json

from src.retention_intelligence import (
    estimate_revenue_exposure,
    generate_retention_recommendations,
    segment_risk,
)


def run():
    print("Testing Retention Intelligence Logic...\n")

    # Mocking predictions for a few sample customers based on Telco logic
    mock_customers = [
        {
            "customerID": "1111-LOW",
            "Contract": "Two year",
            "InternetService": "DSL",
            "TechSupport": "Yes",
            "MonthlyCharges": 30.0,
            "_mock_churn_prob": 0.05,
            "_mock_shap": [{"name": "tenure", "contribution": -1.5}]
        },
        {
            "customerID": "2222-MED",
            "Contract": "Month-to-month",
            "InternetService": "Fiber optic",
            "TechSupport": "No",
            "MonthlyCharges": 95.0,
            "_mock_churn_prob": 0.55,
            "_mock_shap": [{"name": "MonthlyCharges", "contribution": 0.8}]
        },
        {
            "customerID": "3333-HIGH",
            "Contract": "Month-to-month",
            "InternetService": "Fiber optic",
            "TechSupport": "No",
            "MonthlyCharges": 110.0,
            "_mock_churn_prob": 0.85,
            "_mock_shap": [{"name": "MonthlyCharges", "contribution": 1.2}]
        }
    ]

    results = []

    for cust in mock_customers:
        prob = cust["_mock_churn_prob"]
        charges = cust["MonthlyCharges"]

        risk_segment = segment_risk(prob)
        exposure = estimate_revenue_exposure(prob, charges, expected_months=12)
        recs = generate_retention_recommendations(cust, prob, cust["_mock_shap"])

        results.append({
            "customerID": cust["customerID"],
            "Probability": prob,
            "Risk Segment": risk_segment,
            "Annual Revenue Exposure": f"${exposure:.2f}",
            "Recommendations": recs
        })

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    run()
