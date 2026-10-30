"""go/through routing configuration.

Provides endpoints for the go/through customer journey analysis workflow,
including navigation, feature exploration, and SHAP visualization paths.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.data_protection import (
    create_prediction_record,
    get_minimized_features,
    pseudonymize_customer_id,
)
from src.database import get_db
from src.explainability import get_local_explanation
from src.inference import predict_with_threshold
from src.retention_intelligence import (
    estimate_revenue_exposure,
    generate_retention_recommendations,
    segment_risk,
)
from src.schema import (
    ExplainResponse,
    PredictionResponse,
    RecommendationAction,
    RetentionResponse,
    TelcoCustomerFeatures,
)

router = APIRouter(prefix="/go/through", tags=["go/through"])


@router.get("/health", tags=["go/through"])
def go_through_health_check() -> dict[str, str]:
    """Health check for go/through module.

    Returns the status of the go/through service.
    Used by monitoring and load balancers.
    """
    return {"status": "ok", "module": "go/through"}


@router.get("/customer/{customer_id}", tags=["go/through"], response_model=None)
def go_through_customer_detail(
    customer_id: str,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict:
    """Get go/through details for a specific customer.

    Returns customer prediction data, risk segment, and SHAP explanation
    for the go/through workflow.

    Args:
        customer_id: The customer identifier
        db: Database session dependency

    Returns:
        Dictionary with customer prediction and explanation data
    """
    from src.models import PredictionRecord

    # Get the customer's latest prediction
    customer_id_hash = pseudonymize_customer_id(customer_id)

    prediction = (
        db.query(PredictionRecord)
        .filter(PredictionRecord.customer_id_hash == customer_id_hash)
        .order_by(PredictionRecord.created_at.desc())
        .first()
    )

    if not prediction:
        return {
            "customer_id": customer_id,
            "detail": "No prediction found for this customer",
            "churn_probability": None,
            "risk_segment": None,
        }

    # Get raw features with minimization
    raw_features = prediction.raw_features or {}
    minimized = get_minimized_features(raw_features)

    # Build response
    result = {
        "customer_id": customer_id,
        "churn_probability": prediction.churn_probability,
        "churn_prediction": prediction.churn_prediction,
        "risk_segment": prediction.risk_segment,
        "model_version": prediction.model_version,
        "prediction_date": (
            prediction.created_at.isoformat() if prediction.created_at else None
        ),
    }

    # Add minimized features if available
    if minimized:
        result["minimized_features"] = minimized

    return result


@router.post("/predict", response_model=None, tags=["go/through"])
def go_through_predict(
    record: TelcoCustomerFeatures,
    db: Session = Depends(get_db),  # noqa: B008
) -> PredictionResponse:
    """Make a churn prediction as part of the go/through workflow.

    This endpoint is intended for the go/through customer journey flow,
    providing prediction with full response model.

    Args:
        record: Customer feature data
        db: Database session dependency

    Returns:
        Prediction response with churn probability and risk segment
    """
    import pandas as pd

    from src.api import app_state, predict_with_threshold, segment_risk

    df = pd.DataFrame([record.model_dump()])

    try:
        X_transformed = app_state["preprocessor"].transform(df)
        preds, probs = predict_with_threshold(
            app_state["model"], X_transformed, app_state["threshold"]
        )

        prob = float(probs[0])
        pred = int(preds[0])
        risk_segment = segment_risk(prob)

        # Record prediction for monitoring (non-blocking)
        from src.monitoring import log_request_metrics
        log_request_metrics("/go/through/predict", 0.0, 200, {})

        # Persist prediction to database with data minimization
        raw_data = record.model_dump()
        minimized_features = get_minimized_features(raw_data)
        prediction_record = create_prediction_record(
            customer_id=record.customerID,
            churn_probability=prob,
            churn_prediction=pred,
            risk_segment=risk_segment,
            model_version=app_state["version"],
            minimized_features=minimized_features,
        )

        db.add(prediction_record)
        db.commit()
        db.refresh(prediction_record)

        # Create pseudonym lookup for authorized de-pseudonymization
        if prediction_record.customer_id_hash:
            from src.data_protection import create_or_update_pseudonym_lookup
            create_or_update_pseudonym_lookup(
                db, record.customerID, str(prediction_record.customer_id_hash)
            )
            db.commit()

        response = PredictionResponse(
            customerID=record.customerID,
            churn_probability=prob,
            churn_prediction=pred,
            risk_segment=risk_segment,
            model_version=app_state["version"],
        )

        return response

    except Exception as e:
        db.rollback()
        raise Exception(f"Prediction error: {str(e)}") from e


@router.post("/explain", response_model=None, tags=["go/through"])
def go_through_explain(
    record: TelcoCustomerFeatures,
) -> ExplainResponse:
    """Generate SHAP-based explanation as part of the go/through workflow.

    This endpoint provides SHAP explanation for the go/through customer
    journey flow, returning feature contributions and base value.

    Args:
        record: Customer feature data

    Returns:
        Explanation response with base value and feature contributions
    """
    import pandas as pd

    from src.api import app_state

    df = pd.DataFrame([record.model_dump()])

    try:
        X_transformed = app_state["preprocessor"].transform(df)
        explanation = get_local_explanation(
            app_state["explainer"], X_transformed, app_state["feature_names"]
        )

        return ExplainResponse(
            customerID=record.customerID,
            base_value=explanation["base_value"],
            features=explanation["features"],
        )

    except Exception as e:
        raise Exception(f"Explanation error: {str(e)}") from e


@router.post("/retention-recommendation", response_model=None, tags=["go/through"])
def go_through_retention_recommendation(
    record: TelcoCustomerFeatures,
) -> RetentionResponse:
    """Generate retention recommendations as part of the go/through workflow.

    This endpoint provides retention action recommendations based on churn
    risk and SHAP explanation for the go/through customer journey.

    Args:
        record: Customer feature data

    Returns:
        Retention response with risk segment, revenue exposure, and recommendations
    """
    import pandas as pd

    from src.api import app_state

    df = pd.DataFrame([record.model_dump()])
    raw_data = record.model_dump()

    try:
        X_transformed = app_state["preprocessor"].transform(df)

        _, probs = predict_with_threshold(
            app_state["model"], X_transformed, app_state["threshold"]
        )
        prob = float(probs[0])

        explanation = get_local_explanation(
            app_state["explainer"], X_transformed, app_state["feature_names"]
        )
        segment = segment_risk(prob)

        monthly_charges = raw_data.get("MonthlyCharges", 0.0)
        exposure = estimate_revenue_exposure(prob, float(monthly_charges))

        recs_dicts = generate_retention_recommendations(raw_data, prob, explanation["features"])
        recs = [RecommendationAction(action=r["action"], reason=r["reason"]) for r in recs_dicts]

        return RetentionResponse(
            customerID=record.customerID,
            risk_segment=segment,
            annual_revenue_exposure=exposure,
            recommendations=recs,
        )

    except Exception as e:
        raise Exception(f"Retention recommendation error: {str(e)}") from e


@router.get("/workflow-status", tags=["go/through"])
def go_through_workflow_status(
    request: Request,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict:
    """Get go/through workflow status and metrics.

    Returns status information about the go/through workflow including
    prediction counts, risk distribution, and monitoring metrics.

    Args:
        request: FastAPI request object
        db: Database session dependency

    Returns:
        Dictionary with workflow status metrics
    """
    from sqlalchemy import func

    from src.models import PredictionRecord

    try:
        # Get prediction counts
        total_predictions = db.query(func.count(PredictionRecord.id)).scalar() or 0

        # Get risk segment distribution
        risk_counts = db.query(
            PredictionRecord.risk_segment,
            func.count(PredictionRecord.customer_id_hash).label("count")
        ).group_by(PredictionRecord.risk_segment).all()

        risk_distribution = {str(row[0]): int(row[1]) for row in risk_counts}

        # Get recent predictions count (last 24 hours)
        from datetime import datetime, timedelta
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_predictions = db.query(func.count(PredictionRecord.id)).filter(
            PredictionRecord.created_at >= recent_cutoff
        ).scalar() or 0

        return {
            "module": "go/through",
            "total_predictions": int(total_predictions),
            "recent_predictions_24h": int(recent_predictions),
            "risk_distribution": risk_distribution,
            "endpoint": str(request.url.path),
        }

    except Exception as e:
        raise Exception(f"Workflow status error: {str(e)}") from e

