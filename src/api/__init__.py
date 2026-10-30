import hashlib
import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from hmac import compare_digest
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, Optional

import numpy as np
import pandas as pd
from alembic.config import Config as AlembicConfig
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.routes import go_through
from src.config import get_settings
from src.data_protection import (
    create_or_update_pseudonym_lookup,
    create_prediction_record,
    get_minimized_features,
)
from src.database import dispose_engine, get_db, get_pool_status
from src.explainability import get_local_explanation, get_shap_explainer
from src.inference import predict_with_threshold
from src.model_management import (
    get_current_model_version,
    get_model_artifact,
    list_model_versions,
    load_model_artifact,
)
from src.monitoring import MonitoringService, log_request_metrics
from src.retention_intelligence import (
    estimate_revenue_exposure,
    generate_retention_recommendations,
    segment_risk,
)
from src.schema import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    DashboardMetricsResponse,
    ExplainResponse,
    ModelCurrentResponse,
    ModelVersionInfo,
    ModelVersionsResponse,
    PredictionResponse,
    RecommendationAction,
    RetentionResponse,
    TelcoCustomerFeatures,
)


class StructuredLogger:
    """Structured JSON logger for production use."""

    def __init__(self, name: str, level: int = logging.INFO, json_format: bool = True):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.json_format = json_format

        # Avoid duplicate handlers
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(level)
            if json_format:
                formatter = logging.Formatter(
                    '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                    '"logger": "%(name)s", "message": "%(message)s", '
                    '"module": "%(module)s", "function": "%(funcName)s", "line": %(lineno)d}'
                )
            else:
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _log(self, level: int, message: str, **kwargs: Any) -> None:
        if self.json_format and kwargs:
            extra = {k: v for k, v in kwargs.items() if not k.startswith("_")}
            self.logger.log(level, message, extra=extra)
        else:
            self.logger.log(level, message)

    def info(self, message: str, **kwargs: Any) -> None:
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, message, **kwargs)


# Initialize logger based on settings
settings = get_settings()
logger = StructuredLogger(
    __name__,
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    json_format=settings.LOG_FORMAT.lower() == "json",
)

# Prometheus metrics
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint", "status_code"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
PREDICTIONS_TOTAL = Counter(
    "predictions_total",
    "Total number of predictions made",
    ["risk_segment", "model_version"],
)
DRIFT_PSI = Gauge(
    "drift_psi",
    "Population Stability Index (PSI) for prediction drift detection",
)
MODEL_VERSION = Gauge(
    "model_version_info",
    "Current model version info",
    ["version"],
)

# API Key authentication dependency
api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)


def get_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Validate API key from request header.

    In development mode, allows requests without API key for local testing.
    In production, requires valid API key.

    Args:
        api_key: API key from request header

    Returns:
        Validated API key

    Raises:
        HTTPException: If API key is missing or invalid
    """
    if settings.is_production:
        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="Missing API key. Provide valid X-API-Key header.",
            )
        valid_keys = settings.api_keys
        if not valid_keys:
            logger.error("No API keys configured in production")
            raise HTTPException(
                status_code=500,
                detail="Authentication not properly configured",
            )
        # Use constant-time comparison to prevent timing attacks
        # Check against all valid keys (supports rotation via API_KEYS)
        key_valid = any(compare_digest(api_key, valid_key) for valid_key in valid_keys)
        if not key_valid:
            logger.warning("Invalid API key provided")
            raise HTTPException(
                status_code=403,
                detail="Invalid API key",
            )
    return api_key or ""


def require_auth(api_key: str = Depends(get_api_key)) -> str:
    """Dependency that requires valid authentication."""
    return api_key


def get_rate_limit_key(request: Request) -> str:
    """
    Determine rate limit key based on authentication status.

    Uses hashed API key as the primary identifier when available,
    falls back to client IP address for unauthenticated requests.
    """
    # Try to get API key from header
    api_key = request.headers.get(settings.API_KEY_HEADER)
    if api_key:
        # Hash the API key to avoid leaking partial key in logs/metrics
        # Use first 8 chars of SHA-256 for identification
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:8]
        return f"apikey:{key_hash}"
    # Fall back to IP address
    return get_remote_address(request)


# Initialize rate limiter
# In production with multiple workers, Redis is required for shared rate limiting
# In development, Redis is optional - falls back to memory:// with warning
redis_url = settings.REDIS_URL
if redis_url:
    storage_uri = redis_url
    logger.info("Using Redis for distributed rate limiting")
else:
    if settings.is_production:
        logger.warning("REDIS_URL not set; rate limiting will be per-worker only in production")
    else:
        logger.info("REDIS_URL not set; using in-memory rate limiting (development mode)")
    storage_uri = "memory://"

limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[settings.RATE_LIMIT_DEFAULT] if settings.RATE_LIMIT_ENABLED else [],
    storage_uri=storage_uri,
)


def check_pending_migrations() -> bool:
    """
    Check if there are pending database migrations.

    Returns:
        True if there are pending migrations, False otherwise.
    """
    try:
        # Use the app's engine to check migrations
        from src.database import get_engine
        engine = get_engine()

        # Load alembic configuration
        alembic_cfg = AlembicConfig("alembic.ini")
        script = ScriptDirectory.from_config(alembic_cfg)

        # Get current head revision
        heads = script.get_heads()
        if not heads:
            return False

        # Get current revision from database
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()

        # If no current revision, migrations are pending
        if current_rev is None:
            return True

        # Check if current revision matches head
        # For linear history, current should match one of the heads
        return current_rev not in heads

    except Exception as e:
        # On any error, assume migrations might be pending
        logger.warning("Failed to check pending migrations", error=str(e))
        return True


app_state: Dict[str, Any] = {}

# Monitoring service instance (initialized in lifespan)
monitoring_service: Optional[MonitoringService] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global monitoring_service
    try:
        logger.info("Loading model artifact...")
        # In production, require a valid production artifact (not test)
        require_production = settings.is_production
        artifact = get_model_artifact(require_production=require_production)
        app_state["model"] = artifact["model"]
        app_state["preprocessor"] = artifact["preprocessor"]
        app_state["feature_names"] = artifact["feature_names"]
        app_state["threshold"] = artifact["metadata"]["threshold"]
        app_state["version"] = artifact["metadata"]["version"]

        # Set Prometheus model version gauge
        MODEL_VERSION.labels(version=app_state["version"]).set(1)

        logger.info("Initializing SHAP explainer...")
        shap_background = artifact["metadata"].get("shap_background")
        if shap_background:
            background_array = np.array(shap_background)
            logger.info(f"Using SHAP background sample of {len(shap_background)} rows from training data")
        else:
            logger.warning("No shap_background in artifact metadata; falling back to zeros (SHAP base values may be incorrect)")
            background_array = np.zeros((1, len(app_state["feature_names"])))
        app_state["explainer"] = get_shap_explainer(app_state["model"], background_array, app_state["preprocessor"])

        # Initialize monitoring service with reference distribution from training metadata
        ref_predictions = artifact["metadata"].get("reference_predictions", [])
        if not ref_predictions:
            logger.warning("No reference_predictions in artifact metadata; drift detection will be disabled")

        from src.monitoring import DriftConfig, MonitoringService
        monitoring_service = MonitoringService(
            config=DriftConfig(
                reference_predictions=ref_predictions,
                psi_threshold=settings.DRIFT_PSI_THRESHOLD,
                psi_warning=settings.DRIFT_PSI_WARNING,
                ks_threshold=settings.DRIFT_KS_THRESHOLD,
                min_samples=settings.DRIFT_MIN_SAMPLES,
                window_size=settings.DRIFT_WINDOW_SIZE,
                evaluation_interval_sec=settings.DRIFT_EVALUATION_INTERVAL_SEC,
                feature_psi_threshold=settings.DRIFT_FEATURE_PSI_THRESHOLD,
                feature_ks_threshold=settings.DRIFT_FEATURE_KS_THRESHOLD,
                on_drift_result=lambda result: DRIFT_PSI.set(result.psi_score or 0.0) if result.psi_score else None
            ),
            webhook_url=settings.DRIFT_WEBHOOK_URL or None,
            webhook_secret=settings.DRIFT_WEBHOOK_SECRET or None,
            webhook_timeout=settings.DRIFT_WEBHOOK_TIMEOUT
        )
        monitoring_service.start()
        logger.info("Monitoring service started")

        logger.info("Application startup complete.", version=app_state["version"])
        yield
    except Exception as e:
        logger.error("Failed to load model during startup", error=str(e))
        raise e
    finally:
        logger.info("Shutting down application...")
        if monitoring_service:
            monitoring_service.stop()
            logger.info("Monitoring service stopped")
        # Dispose database engine and connection pool
        dispose_engine()
        logger.info("Database engine disposed")
        app_state.clear()
        logger.info("Application shutdown complete.")


app = FastAPI(
    title="Customer Churn Prediction API",
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Health",
            "description": "Health check and readiness endpoints for monitoring and load balancers."
        },
        {
            "name": "Metrics",
            "description": "Prometheus metrics and monitoring endpoints."
        },
        {
            "name": "Model",
            "description": "Model information, metrics, and versioning endpoints."
        },
        {
            "name": "Prediction",
            "description": "Churn prediction endpoints for single and batch predictions."
        },
        {
            "name": "Explainability",
            "description": "SHAP-based model explainability endpoints."
        },
        {
            "name": "Retention",
            "description": "Retention intelligence and recommendation endpoints."
        },
        {
            "name": "Dashboard",
            "description": "Aggregated dashboard metrics for business intelligence."
        },
        {
            "name": "Database",
            "description": "Database connection pool status endpoint."
        },
    ],
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Any]]) -> Any:
        start_time = time.time()
        # Get request ID from request state (set by RequestIDMiddleware)
        request_id = getattr(request.state, "request_id", "unknown")
        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000
            log_request_metrics(request.url.path, process_time, response.status_code, {"request_id": request_id})
            # Record Prometheus metrics
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=str(response.status_code)
            ).observe(process_time / 1000.0)
            return response
        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            log_request_metrics(request.url.path, process_time, 500, {"error": str(e), "request_id": request_id})
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code="500"
            ).observe(process_time / 1000.0)
            raise e


class ModelVersionHeaderMiddleware(BaseHTTPMiddleware):
    """Middleware to add X-Model-Version header to responses."""
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Any]]) -> Any:
        response = await call_next(request)
        # Add model version header if model is loaded
        if "version" in app_state:
            response.headers["X-Model-Version"] = app_state["version"]
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add X-Request-ID header to requests and responses.

    Extracts request ID from X-Request-ID header if present, otherwise generates a new UUID.
    Adds request ID to request state for use in logging and metrics.
    """
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Any]]) -> Any:
        # Extract or generate request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Store in request state for use in route handlers
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(ModelVersionHeaderMiddleware)
app.add_middleware(SlowAPIMiddleware)

# Include go/through routing
app.include_router(go_through.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception", path=str(request.url), error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please contact support."}
    )


@app.get("/health", tags=["Health"])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def health_check(request: Request) -> Dict[str, str]:
    """Public health check endpoint - no authentication required.

    Returns the health status of the API service.
    Used by load balancers and monitoring systems.
    """
    return {"status": "ok"}


@app.get("/ready", tags=["Health"])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def ready_check(request: Request) -> Dict[str, str]:
    """Public readiness check endpoint - no authentication required.

    Returns whether the API is ready to serve predictions (model loaded)
    and database schema is up to date (no pending migrations).
    Used by Kubernetes readiness probes.
    """
    if "model" not in app_state:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    if check_pending_migrations():
        raise HTTPException(status_code=503, detail="Database schema outdated: pending migrations")

    return {"status": "ready"}


@app.get("/metrics", tags=["Metrics"])
def metrics() -> Response:
    """Prometheus metrics endpoint - no authentication required for scraping.

    Exposes Prometheus metrics including:
    - HTTP request duration histograms
    - Prediction counts by risk segment and model version
    - Population drift PSI gauge
    - Model version info
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/model/info", tags=["Model"])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def model_info(request: Request, api_key: str = Depends(require_auth)) -> Dict[str, Any]:
    """Get basic model information.

    Returns the current model version, decision threshold, and feature names.
    Requires authentication.
    """
    if "version" not in app_state:
        raise HTTPException(status_code=503, detail="Model not loaded yet")
    return {
        "version": app_state["version"],
        "threshold": app_state["threshold"],
        "features": app_state["feature_names"]
    }


@app.get("/model/versions", response_model=ModelVersionsResponse, tags=["Model"])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def model_versions(request: Request, api_key: str = Depends(require_auth)) -> ModelVersionsResponse:
    """List all available model versions.

    Returns a list of all model artifacts found in the models directory,
    including version, threshold, timestamp, and test metrics.
    Marks the current production version.
    Requires authentication.
    """
    versions_data = list_model_versions()

    current_version = get_current_model_version()
    versions = []
    for v in versions_data:
        versions.append(ModelVersionInfo(
            version=v["version"],
            threshold=v["threshold"],
            timestamp=v["timestamp"],
            test_roc_auc=v["test_roc_auc"],
            test_recall=v["test_recall"],
            test_precision=v["test_precision"],
            is_current=v["version"] == current_version
        ))

    return ModelVersionsResponse(
        versions=versions,
        current_version=current_version
    )


@app.get("/model/current", response_model=ModelCurrentResponse, tags=["Model"])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def model_current(request: Request, api_key: str = Depends(require_auth)) -> ModelCurrentResponse:
    """Get current production model details.

    Returns detailed information about the currently active production model,
    including feature count and test metrics.
    Requires authentication.
    """
    current_version = get_current_model_version()
    if not current_version:
        raise HTTPException(status_code=404, detail="No production model artifact found")

    # Load the current model artifact to get full details
    versions_data = list_model_versions()
    current_data = next((v for v in versions_data if v["version"] == current_version), None)

    if not current_data:
        raise HTTPException(status_code=404, detail="Current model artifact not found")

    # Load artifact for feature count
    artifact = load_model_artifact(current_data["filepath"], verify_integrity=False)
    feature_count = len(artifact.get("feature_names", []))

    return ModelCurrentResponse(
        version=current_data["version"],
        threshold=current_data["threshold"],
        timestamp=current_data["timestamp"],
        test_roc_auc=current_data["test_roc_auc"],
        test_recall=current_data["test_recall"],
        test_precision=current_data["test_precision"],
        feature_count=feature_count
    )


@app.get("/dashboard/metrics", response_model=DashboardMetricsResponse, tags=["Dashboard"])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def dashboard_metrics(request: Request, db: Session = Depends(get_db), api_key: str = Depends(require_auth)) -> DashboardMetricsResponse:  # noqa: B008
    """Get aggregated dashboard metrics from prediction records.

    Returns business intelligence metrics including:
    - Total unique customers
    - Risk segment distribution (High/Medium/Low)
    - Annual revenue at risk
    Requires authentication.
    """
    from sqlalchemy import func

    from src.models import PredictionRecord

    try:
        # Get total predictions (unique customers by hash)
        total_customers = db.query(func.count(func.distinct(PredictionRecord.customer_id_hash))).scalar() or 0

        # Get risk segment counts
        risk_counts = db.query(
            PredictionRecord.risk_segment,
            func.count(func.distinct(PredictionRecord.customer_id_hash))
        ).group_by(PredictionRecord.risk_segment).all()

        risk_distribution: dict[str, int] = {str(row[0]): int(row[1]) for row in risk_counts}
        high_risk = risk_distribution.get("High Risk", 0)
        medium_risk = risk_distribution.get("Medium Risk", 0)
        low_risk = risk_distribution.get("Low Risk", 0)

        # Calculate revenue at risk (sum of monthly charges * 12 for high/medium risk)
        # We need to get the latest prediction for each customer with their features
        subquery = db.query(
            PredictionRecord.customer_id_hash,
            func.max(PredictionRecord.created_at).label('max_created_at')
        ).group_by(PredictionRecord.customer_id_hash).subquery()

        latest_predictions = db.query(PredictionRecord).join(
            subquery,
            (PredictionRecord.customer_id_hash == subquery.c.customer_id_hash) &
            (PredictionRecord.created_at == subquery.c.max_created_at)
        ).filter(
            PredictionRecord.risk_segment.in_(["High Risk", "Medium Risk"])
        ).all()

        annual_revenue_at_risk = 0.0
        for pred in latest_predictions:
            if pred.raw_features and 'MonthlyCharges' in pred.raw_features:
                monthly_charges = float(pred.raw_features['MonthlyCharges'])
                annual_revenue_at_risk += monthly_charges * 12

        return DashboardMetricsResponse(
            total_customers=total_customers,
            high_risk_customers=high_risk,
            medium_risk_customers=medium_risk,
            low_risk_customers=low_risk,
            annual_revenue_at_risk=annual_revenue_at_risk,
            risk_distribution=risk_distribution
        )
    except Exception as e:
        logger.error("Dashboard metrics error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard metrics") from e


@app.get("/db/pool", tags=["Database"])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def db_pool_status(request: Request, api_key: str = Depends(require_auth)) -> Dict[str, Any]:
    """Get database connection pool status for monitoring.

    Returns connection pool statistics including pool size, checked out connections,
    overflow, and pool health metrics.
    Requires authentication.
    """
    try:
        return get_pool_status()
    except Exception as e:
        logger.error("Failed to get pool status", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get pool status") from e


@app.post("/predict", response_model=PredictionResponse, tags=["Prediction"])
@limiter.limit(settings.RATE_LIMIT_PREDICT)
def predict(request: Request, record: TelcoCustomerFeatures, db: Session = Depends(get_db), api_key: str = Depends(require_auth)) -> PredictionResponse:  # noqa: B008
    """Predict churn probability for a single customer.

    Takes customer features and returns:
    - Churn probability (0-1)
    - Binary churn prediction (0/1)
    - Risk segment (Low/Medium/High)
    - Model version used

    Also stores the prediction with pseudonymized customer ID for monitoring.
    Requires authentication.
    """
    df = pd.DataFrame([record.model_dump()])

    try:
        X_transformed = app_state["preprocessor"].transform(df)
        preds, probs = predict_with_threshold(app_state["model"], X_transformed, app_state["threshold"])

        prob = float(probs[0])
        pred = int(preds[0])
        risk_segment = segment_risk(prob)

        # Record prediction for population-level drift monitoring (non-blocking)
        if monitoring_service:
            monitoring_service.record_prediction(prob)

        # Record Prometheus metrics
        PREDICTIONS_TOTAL.labels(
            risk_segment=risk_segment,
            model_version=app_state["version"]
        ).inc()

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

        # Create/update pseudonym lookup for authorized de-pseudonymization
        if prediction_record.customer_id_hash:
            create_or_update_pseudonym_lookup(db, record.customerID, str(prediction_record.customer_id_hash))
            db.commit()

        response = PredictionResponse(
            customerID=record.customerID,
            churn_probability=prob,
            churn_prediction=pred,
            risk_segment=segment_risk(prob),
            model_version=app_state["version"]
        )
        # Add model version header for client-side version tracking
        request.state.model_version = app_state["version"]
        return response
    except Exception as e:
        db.rollback()
        logger.error("Prediction error", customer_id=record.customerID, error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/predict/batch", response_model=BatchPredictionResponse, tags=["Prediction"])
@limiter.limit(settings.RATE_LIMIT_BATCH)
def predict_batch(request: Request, request_body: BatchPredictionRequest, db: Session = Depends(get_db), api_key: str = Depends(require_auth)) -> BatchPredictionResponse:  # noqa: B008
    """Predict churn probability for multiple customers in a single request.

    Accepts up to 100 customers per request.
    Returns a list of predictions with the same fields as single prediction.
    Requires authentication.
    """
    if not request_body.customers:
        raise HTTPException(status_code=400, detail="Empty customer list")

    df = pd.DataFrame([r.model_dump() for r in request_body.customers])

    try:
        X_transformed = app_state["preprocessor"].transform(df)
        preds, probs = predict_with_threshold(app_state["model"], X_transformed, app_state["threshold"])

        responses = []
        for i, record in enumerate(request_body.customers):
            prob = float(probs[i])
            risk_segment = segment_risk(prob)

            # Record prediction for population-level drift monitoring
            if monitoring_service:
                monitoring_service.record_prediction(prob)

            # Record Prometheus metrics
            PREDICTIONS_TOTAL.labels(
                risk_segment=risk_segment,
                model_version=app_state["version"]
            ).inc()

            # Persist prediction to database with data minimization
            raw_data = record.model_dump()
            minimized_features = get_minimized_features(raw_data)
            prediction_record = create_prediction_record(
                customer_id=record.customerID,
                churn_probability=prob,
                churn_prediction=int(preds[i]),
                risk_segment=segment_risk(prob),
                model_version=app_state["version"],
                minimized_features=minimized_features,
            )
            db.add(prediction_record)

            # Create/update pseudonym lookup for authorized de-pseudonymization
            if prediction_record.customer_id_hash:
                create_or_update_pseudonym_lookup(db, record.customerID, str(prediction_record.customer_id_hash))

            responses.append(PredictionResponse(
                customerID=record.customerID,
                churn_probability=prob,
                churn_prediction=int(preds[i]),
                risk_segment=segment_risk(prob),
                model_version=app_state["version"]
            ))

        db.commit()
        return BatchPredictionResponse(predictions=responses)
    except Exception as e:
        db.rollback()
        logger.error("Batch prediction error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/explain", response_model=ExplainResponse, tags=["Explainability"])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def explain(request: Request, record: TelcoCustomerFeatures, api_key: str = Depends(require_auth)) -> ExplainResponse:
    """Generate SHAP-based explanation for a single prediction.

    Returns:
    - Base value (expected model output)
    - Feature contributions ranked by absolute magnitude

    Uses LinearExplainer for Logistic Regression with validation set background.
    Requires authentication.
    """
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
        logger.error("Explanation error", customer_id=record.customerID, error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/retention-recommendation", response_model=RetentionResponse, tags=["Retention"])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
def retention_recommendation(request: Request, record: TelcoCustomerFeatures, api_key: str = Depends(require_auth)) -> RetentionResponse:
    """Generate retention recommendations based on churn risk and SHAP explanations.

    Returns:
    - Risk segment
    - Annual revenue exposure
    - Prioritized list of retention actions with reasons

    Uses rule-based logic driven by top SHAP feature contributions.
    Requires authentication.
    """
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
        logger.error("Retention intelligence error", customer_id=record.customerID, error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e
