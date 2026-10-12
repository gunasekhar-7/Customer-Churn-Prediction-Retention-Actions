import logging
from contextlib import asynccontextmanager

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from src.explainability import get_local_explanation, get_shap_explainer
from src.inference import predict_with_threshold
from src.model_management import get_model_artifact
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
    RetentionResponse,
    TelcoCustomerRecord,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app_state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
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

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please contact support."}
    )

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/ready")
def ready_check():
    if "model" in app_state:
        return {"status": "ready"}
    raise HTTPException(status_code=503, detail="Model not loaded yet")

@app.get("/model/info")
def model_info():
    if "version" not in app_state:
         raise HTTPException(status_code=503, detail="Model not loaded yet")
    return {
        "version": app_state["version"],
        "threshold": app_state["threshold"],
        "features": app_state["feature_names"]
    }

@app.post("/predict", response_model=PredictionResponse)
def predict(record: TelcoCustomerRecord):
    df = pd.DataFrame([record.model_dump()])

    try:
        X_transformed = app_state["preprocessor"].transform(df)
        preds, probs = predict_with_threshold(app_state["model"], X_transformed, app_state["threshold"])

        prob = float(probs[0])
        pred = int(preds[0])

        return PredictionResponse(
            customerID=record.customerID,
            churn_probability=prob,
            churn_prediction=pred,
            risk_segment=segment_risk(prob),
            model_version=app_state["version"]
        )
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e

@app.post("/predict/batch", response_model=BatchPredictionResponse)
def predict_batch(request: BatchPredictionRequest):
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
def explain(record: TelcoCustomerRecord):
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
def retention_recommendation(record: TelcoCustomerRecord):
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

        recs = generate_retention_recommendations(raw_data, prob, explanation["features"])

        return RetentionResponse(
            customerID=record.customerID,
            risk_segment=segment,
            annual_revenue_exposure=exposure,
            recommendations=recs
        )
    except Exception as e:
        logger.error(f"Retention intelligence error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
