import pytest
from sqlalchemy import create_engine

from src.database import (
    dispose_engine,
    get_db,
    get_pool_status,
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
    import hashlib
    customer_id_hash = hashlib.sha256("test-salt:TEST-1".encode('utf-8')).hexdigest()
    pred = PredictionRecord(
        customer_id_hash=customer_id_hash,
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
    assert pred.customer_id_hash == customer_id_hash
    assert pred.risk_segment == "High"

def test_create_retention_recommendation_record(db_session):
    import hashlib
    customer_id_hash = hashlib.sha256("test-salt:TEST-2".encode('utf-8')).hexdigest()
    pred = PredictionRecord(
        customer_id_hash=customer_id_hash,
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
    assert rec.prediction_record.customer_id_hash == customer_id_hash

def test_get_db_generator():
    db_gen = get_db()
    db = next(db_gen)
    assert db is not None
    try:
        next(db_gen)
    except StopIteration:
        pass

def test_dispose_engine():
    """Test engine disposal works correctly."""
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    set_engine(test_engine)
    init_database()

    # Verify engine is set
    from src.database import get_engine
    assert get_engine() is test_engine

    # Dispose
    dispose_engine()

    # After disposal, get_engine should create a new one
    new_engine = get_engine()
    assert new_engine is not test_engine

    # Cleanup
    dispose_engine()

def test_get_pool_status():
    """Test pool status returns expected keys."""
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    set_engine(test_engine)

    status = get_pool_status()
    assert "size" in status
    assert "checked_out" in status
    assert "overflow" in status
    assert "total" in status
    # For SQLite, pool attributes are ints, not methods
    assert isinstance(status["size"], int)
    assert isinstance(status["checked_out"], int)
    assert isinstance(status["overflow"], int)
    assert isinstance(status["total"], int)

    dispose_engine()

def test_set_engine_replaces_session_factory():
    """Test that set_engine replaces the session factory."""
    from src.database import get_session_factory
    engine1 = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    engine2 = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    set_engine(engine1)
    factory1 = get_session_factory()

    set_engine(engine2)
    factory2 = get_session_factory()

    assert factory1 is not factory2

    dispose_engine()
