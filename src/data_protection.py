"""
Customer Data Protection and Minimization Utilities.

This module provides utilities for:
1. Minimizing customer data stored in prediction records
2. Identifying sensitive fields that should not be persisted
3. Retention policy enforcement
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models import PredictionRecord, RetentionRecommendationRecord

logger = logging.getLogger(__name__)

# Fields that are considered sensitive and should NOT be stored in raw_features
# These contain direct identifiers, financial data, or demographic information
SENSITIVE_FIELDS: Set[str] = {
    "customerID",           # Direct identifier
    "MonthlyCharges",       # Financial
    "TotalCharges",         # Financial
    "PaymentMethod",        # Billing/Financial
    "Contract",             # Contractual
    "PaperlessBilling",     # Billing preference
    "gender",               # Demographic
    "SeniorCitizen",        # Demographic (age indicator)
    "Partner",              # Household
    "Dependents",           # Household
    "PhoneService",         # Service usage (could be identifying in combination)
    "MultipleLines",        # Service usage
    "InternetService",      # Service usage
    "OnlineSecurity",       # Service usage
    "OnlineBackup",         # Service usage
    "DeviceProtection",     # Service usage
    "TechSupport",          # Service usage
    "StreamingTV",          # Service usage
    "StreamingMovies",      # Service usage
    "Churn",                # Target variable (ground truth)
}

# Fields that are SAFE to store (non-sensitive, useful for monitoring/explainability)
SAFE_FIELDS: Set[str] = {
    "tenure",               # Non-identifying, useful for drift monitoring
}

# Fields needed for explainability (SHAP feature values)
# These are the transformed feature names, not raw customer data
EXPLAINABILITY_FIELDS: Set[str] = set()

# Fields required for business logic (retention recommendations)
BUSINESS_REQUIRED_FIELDS: Set[str] = {
    "Contract",             # Needed for "Offer Annual Upgrade Discount"
    "MonthlyCharges",       # Needed for revenue exposure calculation
    "InternetService",      # Needed for "Offer Free Tech Support" rule
    "TechSupport",          # Needed for "Offer Free Tech Support" rule
}


def get_minimized_features(
    raw_data: Dict[str, Any],
    include_business_fields: bool = True,
) -> Dict[str, Any]:
    """
    Extract only non-sensitive fields from raw customer data for persistence.

    Args:
        raw_data: The complete customer record from the API request.
        include_business_fields: If True, include fields needed for business logic
                                 (retention recommendations, revenue exposure).

    Returns:
        Dictionary containing only safe/minimized fields for persistence.
    """
    settings = get_settings()

    if not settings.DATA_MINIMIZATION_ENABLED:
        # Return all fields if minimization is disabled (for backward compatibility)
        return raw_data

    minimized = {}

    # Always include safe fields
    for field in SAFE_FIELDS:
        if field in raw_data:
            minimized[field] = raw_data[field]

    # Include business-required fields if enabled
    if include_business_fields:
        for field in BUSINESS_REQUIRED_FIELDS:
            if field in raw_data:
                minimized[field] = raw_data[field]

    # Add metadata about minimization
    minimized["_minimized"] = True
    minimized["_minimized_at"] = datetime.now(timezone.utc).isoformat()
    minimized["_original_field_count"] = len(raw_data)
    minimized["_retained_field_count"] = len(minimized) - 3  # Exclude metadata fields

    return minimized


def get_sensitive_fields(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract sensitive fields that should NOT be persisted.

    Useful for auditing what data is being excluded.

    Args:
        raw_data: The complete customer record.

    Returns:
        Dictionary of sensitive fields found in the input.
    """
    return {
        field: raw_data[field]
        for field in SENSITIVE_FIELDS
        if field in raw_data
    }


def create_prediction_record(
    customer_id: str,
    churn_probability: float,
    churn_prediction: int,
    risk_segment: str,
    model_version: str,
    raw_features: Optional[Dict[str, Any]] = None,
    minimized_features: Optional[Dict[str, Any]] = None,
) -> PredictionRecord:
    """
    Create a PredictionRecord with proper data minimization.

    Args:
        customer_id: Customer identifier.
        churn_probability: Predicted churn probability.
        churn_prediction: Binary prediction (0 or 1).
        risk_segment: Risk segment (Low, Medium, High).
        model_version: Model version used for prediction.
        raw_features: Original raw features (will be minimized if provided).
        minimized_features: Pre-minimized features (used if raw_features not provided).

    Returns:
        PredictionRecord instance with minimized data.
    """
    settings = get_settings()

    if minimized_features is not None:
        features_to_store = minimized_features
    elif raw_features is not None and settings.DATA_MINIMIZATION_ENABLED:
        features_to_store = get_minimized_features(raw_features)
    elif raw_features is not None:
        features_to_store = raw_features
    else:
        features_to_store = None

    return PredictionRecord(
        customer_id=customer_id,
        churn_probability=churn_probability,
        churn_prediction=churn_prediction,
        risk_segment=risk_segment,
        model_version=model_version,
        raw_features=features_to_store,
    )


def cleanup_expired_records(
    db: Session,
    retention_days: Optional[int] = None,
    batch_size: Optional[int] = None,
    dry_run: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Delete or anonymize prediction records older than the retention period.

    This function:
    1. Finds records older than the retention period
    2. Processes them in batches to avoid long transactions
    3. Deletes associated retention recommendations first (FK constraint)
    4. Deletes the prediction records
    5. Returns statistics about the cleanup

    Args:
        db: Database session.
        retention_days: Override retention period (uses config default if None).
        batch_size: Override batch size (uses config default if None).
        dry_run: If True, only log what would be deleted without deleting.

    Returns:
        Dictionary with cleanup statistics.
    """
    settings = get_settings()

    retention_days = retention_days or settings.DATA_RETENTION_DAYS
    batch_size = batch_size or settings.DATA_RETENTION_BATCH_SIZE
    dry_run = dry_run if dry_run is not None else settings.DATA_RETENTION_DRY_RUN

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

    logger.info(
        "Starting data retention cleanup",
        extra={
            "cutoff_date": cutoff_date.isoformat(),
            "retention_days": retention_days,
            "batch_size": batch_size,
            "dry_run": dry_run,
        }
    )

    total_deleted = 0
    total_recommendations_deleted = 0
    batch_count = 0

    while True:
        # Find expired prediction records (with limit for batching)
        expired_query: Any = (
            select(PredictionRecord.id)
            .where(PredictionRecord.created_at < cutoff_date)  # type: ignore[arg-type]
            .limit(batch_size)
        )
        expired_ids = [row[0] for row in db.execute(expired_query).fetchall()]  # type: ignore[attr-defined]

        if not expired_ids:
            break

        batch_count += 1
        logger.info(
            f"Processing batch {batch_count}: {len(expired_ids)} records",
            extra={"batch": batch_count, "record_count": len(expired_ids)}
        )

        if not dry_run:
            # Delete associated retention recommendations first (FK constraint)
            rec_delete = delete(RetentionRecommendationRecord).where(
                RetentionRecommendationRecord.prediction_record_id.in_(expired_ids)
            )
            rec_result = db.execute(rec_delete)
            total_recommendations_deleted += rec_result.rowcount

            # Delete prediction records
            pred_delete = delete(PredictionRecord).where(
                PredictionRecord.id.in_(expired_ids)
            )
            pred_result = db.execute(pred_delete)
            total_deleted += pred_result.rowcount

            db.commit()
        else:
            # In dry run, just count what would be deleted
            rec_count_query: Any = select(RetentionRecommendationRecord.id).where(
                RetentionRecommendationRecord.prediction_record_id.in_(expired_ids)
            )
            rec_count = len(db.execute(rec_count_query).fetchall())
            total_recommendations_deleted += rec_count
            total_deleted += len(expired_ids)

        # If we got fewer than batch_size, we're done
        if len(expired_ids) < batch_size:
            break

    result = {
        "deleted_prediction_records": total_deleted,
        "deleted_recommendations": total_recommendations_deleted,
        "batches_processed": batch_count,
        "cutoff_date": cutoff_date.isoformat(),
        "retention_days": retention_days,
        "dry_run": dry_run,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "Data retention cleanup completed",
        extra=result
    )

    return result


def get_retention_stats(db: Session, retention_days: Optional[int] = None) -> Dict[str, Any]:
    """
    Get statistics about records that would be affected by cleanup.

    Args:
        db: Database session.
        retention_days: Override retention period (uses config default if None).

    Returns:
        Dictionary with statistics about expired vs active records.
    """
    settings = get_settings()
    retention_days = retention_days or settings.DATA_RETENTION_DAYS
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

    # Count expired records
    expired_count: Any = db.execute(
        select(PredictionRecord.id).where(PredictionRecord.created_at < cutoff_date)  # type: ignore[arg-type]
    ).fetchall()

    # Count total records
    total_count: Any = db.execute(select(PredictionRecord.id)).fetchall()

    # Count expired recommendations
    expired_rec_count: Any = db.execute(
        select(RetentionRecommendationRecord.id)
        .join(PredictionRecord)
        .where(PredictionRecord.created_at < cutoff_date)  # type: ignore[arg-type]
    ).fetchall()

    total_rec_count: Any = db.execute(select(RetentionRecommendationRecord.id)).fetchall()

    return {
        "total_prediction_records": len(total_count),
        "expired_prediction_records": len(expired_count),
        "active_prediction_records": len(total_count) - len(expired_count),
        "total_recommendations": len(total_rec_count),
        "expired_recommendations": len(expired_rec_count),
        "active_recommendations": len(total_rec_count) - len(expired_rec_count),
        "retention_days": retention_days,
        "cutoff_date": cutoff_date.isoformat(),
    }
