import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models import PredictionRecord, RetentionRecommendationRecord

# In-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="module")
def engine():
    return create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

@pytest.fixture(scope="module")
def tables(engine):
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(engine, tables):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()

def test_create_prediction_record(db_session):
    pred = PredictionRecord(
        customer_id="TEST-1",
        churn_probability=0.85,
        churn_prediction=1,
        risk_segment="High",
        model_version="1.0.0",
        raw_features={"tenure": 1}
    )
    db_session.add(pred)
    db_session.commit()
    db_session.refresh(pred)

    assert pred.id is not None
    assert pred.customer_id == "TEST-1"
    assert pred.risk_segment == "High"

def test_create_retention_recommendation_record(db_session):
    # First need a prediction record
    pred = PredictionRecord(
        customer_id="TEST-2",
        churn_probability=0.5,
        churn_prediction=0,
        risk_segment="Medium",
        model_version="1.0.0"
    )
    db_session.add(pred)
    db_session.commit()

    rec = RetentionRecommendationRecord(
        prediction_record_id=pred.id,
        action="Offer Discount",
        reason="Medium risk customer"
    )
    db_session.add(rec)
    db_session.commit()
    db_session.refresh(rec)

    assert rec.id is not None
    assert rec.action == "Offer Discount"
    assert rec.prediction_record.customer_id == "TEST-2"
