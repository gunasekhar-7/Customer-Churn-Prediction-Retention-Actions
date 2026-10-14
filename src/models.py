from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from src.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PredictionRecord(Base):
    __tablename__ = "prediction_records"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, index=True, nullable=False)
    churn_probability = Column(Float, nullable=False)
    churn_prediction = Column(Integer, nullable=False)
    risk_segment = Column(String, nullable=False)
    model_version = Column(String, nullable=False)
    created_at = Column(DateTime, default=utc_now, index=True)  # Indexed for retention cleanup queries

    # Minimized features stored as JSON for auditing/explainability
    # Contains only non-sensitive fields needed for monitoring and business logic
    raw_features = Column(JSON, nullable=True)

    recommendations = relationship("RetentionRecommendationRecord", back_populates="prediction_record", cascade="all, delete-orphan")

    # Composite index for efficient retention queries
    __table_args__ = (
        Index('ix_prediction_records_created_at_customer_id', 'created_at', 'customer_id'),
    )


class RetentionRecommendationRecord(Base):
    __tablename__ = "retention_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    prediction_record_id = Column(Integer, ForeignKey("prediction_records.id"), nullable=False)
    action = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    prediction_record = relationship("PredictionRecord", back_populates="recommendations")
