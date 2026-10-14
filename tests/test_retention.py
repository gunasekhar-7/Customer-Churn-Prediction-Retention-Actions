import pytest

from src.retention_intelligence import (
    estimate_revenue_exposure,
    generate_retention_recommendations,
    segment_risk,
)


def test_segment_risk():
    assert segment_risk(0.1) == "Low"
    assert segment_risk(0.5) == "Medium"
    assert segment_risk(0.8) == "High"

def test_estimate_revenue_exposure():
    # 50% prob * $100 * 12 months = $600 exposure
    assert estimate_revenue_exposure(0.5, 100.0) == 600.0
    # Overwrite months to 1
    assert estimate_revenue_exposure(0.8, 50.0, expected_months=1) == 40.0

    with pytest.raises(ValueError):
        estimate_revenue_exposure(-0.1, 100)
    with pytest.raises(ValueError):
        estimate_revenue_exposure(0.5, -100)

def test_generate_retention_recommendations():
    # Low risk bypass
    low_risk_recs = generate_retention_recommendations({}, 0.1, [])
    assert len(low_risk_recs) == 1
    assert "Maintain" in low_risk_recs[0]["action"]

    # High risk, Month-to-month, High charges driver
    customer_data = {
        "Contract": "Month-to-month",
        "InternetService": "DSL",
        "TechSupport": "No"
    }
    shap_features = [
        {"name": "MonthlyCharges", "contribution": 1.2},
        {"name": "tenure", "contribution": -0.5}
    ]
    recs = generate_retention_recommendations(customer_data, 0.8, shap_features)
    assert len(recs) == 2
    actions = [r["action"] for r in recs]
    assert "Offer Annual Upgrade Discount" in actions
    assert "Offer $10 Monthly Loyalty Credit" in actions

    # Fiber optic no tech support
    fiber_customer = {
        "Contract": "Two year",
        "InternetService": "Fiber optic",
        "TechSupport": "No"
    }
    fiber_recs = generate_retention_recommendations(fiber_customer, 0.7, [{"name": "Dummy", "contribution": 0.1}])
    actions = [r["action"] for r in fiber_recs]
    assert "Offer Free Tech Support Add-on for 3 months" in actions


def test_generate_retention_high_fallback():
    # Covers line 75: High risk but no specific rules trigger -> fallback to agent
    customer_data = {"Contract": "Two year", "InternetService": "DSL", "TechSupport": "Yes"}
    shap_features = [{"name": "Dummy", "contribution": 0.1}]
    recs = generate_retention_recommendations(customer_data, 0.9, shap_features)
    assert len(recs) == 1
    assert "Trigger Personal Agent Call" in recs[0]["action"]
