import pytest
from sqlalchemy import create_engine

from src.database import (
    dispose_engine,
    get_db,
    init_database,
    set_engine,
)
from src.models import PredictionRecord, RetentionRecommendationRecord

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="module")
def engine():
    return create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})


@pytest.fixture(scope="module")
def tables(engine):
    set_engine(engine)
    init_database()
    yield
    dispose_engine()


@pytest.fixture
def db_session(engine, tables):
    from src.database import get_session_factory
    SessionLocal = get_session_factory()
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

def test_get_db_generator():
    db_gen = get_db()
    db = next(db_gen)
    assert db is not None
    try:
        next(db_gen)
    except StopIteration:
        pass
