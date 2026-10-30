from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from src.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PredictionRecord(Base):
    __tablename__ = "prediction_records"

    id = Column(Integer, primary_key=True, index=True)
    customer_id_hash = Column(String(64), index=True, nullable=True)  # Salted SHA-256 pseudonym
    churn_probability = Column(Float, nullable=False)
    churn_prediction = Column(Integer, nullable=False)
    risk_segment = Column(String, nullable=False)
    model_version = Column(String, nullable=False)
    # Use timezone-aware DateTime for PostgreSQL, SQLite will store as UTC string
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)

    # Minimized features stored as JSON for auditing/explainability
    # Contains only non-sensitive fields needed for monitoring and business logic
    raw_features = Column(JSON, nullable=True)

    recommendations = relationship("RetentionRecommendationRecord", back_populates="prediction_record", cascade="all, delete-orphan")


class CustomerPseudonymLookup(Base):
    """
    Lookup table for authorized customer ID de-pseudonymization.

    Stores the mapping between customer_id_hash and customer_id for
    authorized personnel to resolve pseudonyms when legally required.
    Access to this table should be strictly controlled via RBAC.
    """
    __tablename__ = "customer_pseudonym_lookup"

    id = Column(Integer, primary_key=True, index=True)
    customer_id_hash = Column(String(64), unique=True, index=True, nullable=False)
    customer_id = Column(String, nullable=False)  # Original customer ID (encrypted in production)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    access_count = Column(Integer, default=0)

    # Ensure one lookup entry per customer
    __table_args__ = (
        UniqueConstraint('customer_id_hash', name='uq_customer_pseudonym_hash'),
    )


class RetentionRecommendationRecord(Base):
    __tablename__ = "retention_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    prediction_record_id = Column(Integer, ForeignKey("prediction_records.id"), nullable=False)
    action = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    prediction_record = relationship("PredictionRecord", back_populates="recommendations")
