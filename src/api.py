import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from src.data_protection import create_prediction_record, get_minimized_features
from src.database import get_db
from src.explainability import get_local_explanation, get_shap_explainer
from src.inference import predict_with_threshold
from src.model_management import get_model_artifact
from src.monitoring import check_drift_thresholds, log_request_metrics
from src.retention_intelligence import (
    estimate_revenue_exposure,
    generate_retention_recommendations,
    segment_risk,
)
from src.schema import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    ExplainResponse,
    PredictionResponse,
    RecommendationAction,
    RetentionResponse,
    TelcoCustomerRecord,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app_state: Dict[str, Any] = {}

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    try:
        logger.info("Loading model artifact...")
        artifact = get_model_artifact()
        app_state["model"] = artifact["model"]
        app_state["preprocessor"] = artifact["preprocessor"]
        app_state["feature_names"] = artifact["feature_names"]
        app_state["threshold"] = artifact["metadata"]["threshold"]
        app_state["version"] = artifact["metadata"]["version"]

        logger.info("Initializing SHAP explainer...")
        dummy_background = np.zeros((1, len(app_state["feature_names"])))
        app_state["explainer"] = get_shap_explainer(app_state["model"], dummy_background)

        logger.info("Application startup complete.")
        yield
    except Exception as e:
        logger.error(f"Failed to load model during startup: {e}")
        raise e
    finally:
        app_state.clear()
        logger.info("Application shutdown.")

app = FastAPI(
    title="Customer Churn Prediction API",
    version="1.0.0",
    lifespan=lifespan
)

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Any]]) -> Any:
        start_time = time.time()
        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000
            log_request_metrics(request.url.path, process_time, response.status_code)
            return response
        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            log_request_metrics(request.url.path, process_time, 500, {"error": str(e)})
            raise e

app.add_middleware(MetricsMiddleware)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please contact support."}
    )

@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}

@app.get("/ready")
def ready_check() -> Dict[str, str]:
    if "model" in app_state:
        return {"status": "ready"}
    raise HTTPException(status_code=503, detail="Model not loaded yet")

@app.get("/model/info")
def model_info() -> Dict[str, Any]:
    if "version" not in app_state:
         raise HTTPException(status_code=503, detail="Model not loaded yet")
    return {
        "version": app_state["version"],
        "threshold": app_state["threshold"],
        "features": app_state["feature_names"]
    }

@app.post("/predict", response_model=PredictionResponse)
def predict(record: TelcoCustomerRecord, db: Session = Depends(get_db)) -> PredictionResponse:  # noqa: B008
    df = pd.DataFrame([record.model_dump()])

    try:
        X_transformed = app_state["preprocessor"].transform(df)
        preds, probs = predict_with_threshold(app_state["model"], X_transformed, app_state["threshold"])

        prob = float(probs[0])
        pred = int(preds[0])

        check_drift_thresholds(prob)

        # Persist prediction to database with data minimization
        raw_data = record.model_dump()
        minimized_features = get_minimized_features(raw_data)
        prediction_record = create_prediction_record(
            customer_id=record.customerID,
            churn_probability=prob,
            churn_prediction=pred,
            risk_segment=segment_risk(prob),
            model_version=app_state["version"],
            minimized_features=minimized_features,
        )
        db.add(prediction_record)
        db.commit()
        db.refresh(prediction_record)

        return PredictionResponse(
            customerID=record.customerID,
            churn_probability=prob,
            churn_prediction=pred,
            risk_segment=segment_risk(prob),
            model_version=app_state["version"]
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e

@app.post("/predict/batch", response_model=BatchPredictionResponse)
def predict_batch(request: BatchPredictionRequest) -> BatchPredictionResponse:
    if not request.customers:
        raise HTTPException(status_code=400, detail="Empty customer list")

    df = pd.DataFrame([r.model_dump() for r in request.customers])

    try:
        X_transformed = app_state["preprocessor"].transform(df)
        preds, probs = predict_with_threshold(app_state["model"], X_transformed, app_state["threshold"])

        responses = []
        for i, record in enumerate(request.customers):
            prob = float(probs[i])
            responses.append(PredictionResponse(
                customerID=record.customerID,
                churn_probability=prob,
                churn_prediction=int(preds[i]),
                risk_segment=segment_risk(prob),
                model_version=app_state["version"]
            ))

        return BatchPredictionResponse(predictions=responses)
    except Exception as e:
        logger.error(f"Batch prediction error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e

@app.post("/explain", response_model=ExplainResponse)
def explain(record: TelcoCustomerRecord) -> ExplainResponse:
    df = pd.DataFrame([record.model_dump()])

    try:
        X_transformed = app_state["preprocessor"].transform(df)
        explanation = get_local_explanation(app_state["explainer"], X_transformed, app_state["feature_names"])

        return ExplainResponse(
            customerID=record.customerID,
            base_value=explanation["base_value"],
            features=explanation["features"]
        )
    except Exception as e:
        logger.error(f"Explanation error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e

@app.post("/retention-recommendation", response_model=RetentionResponse)
def retention_recommendation(record: TelcoCustomerRecord) -> RetentionResponse:
    df = pd.DataFrame([record.model_dump()])
    raw_data = record.model_dump()

    try:
        X_transformed = app_state["preprocessor"].transform(df)

        _, probs = predict_with_threshold(app_state["model"], X_transformed, app_state["threshold"])
        prob = float(probs[0])

        explanation = get_local_explanation(app_state["explainer"], X_transformed, app_state["feature_names"])
        segment = segment_risk(prob)

        monthly_charges = raw_data.get('MonthlyCharges', 0.0)
        exposure = estimate_revenue_exposure(prob, float(monthly_charges))

        recs_dicts = generate_retention_recommendations(raw_data, prob, explanation["features"])
        recs = [RecommendationAction(action=r["action"], reason=r["reason"]) for r in recs_dicts]

        return RetentionResponse(
            customerID=record.customerID,
            risk_segment=segment,
            annual_revenue_exposure=exposure,
            recommendations=recs
        )
    except Exception as e:
        logger.error(f"Retention intelligence error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
