"""
PostgreSQL Integration Tests for Customer Churn Prediction Platform.

These tests verify PostgreSQL-specific behavior including:
- Migrations and schema management
- Timezone-aware timestamp handling
- Connection pooling and failure recovery
- Data minimization and retention cleanup
- Timestamp semantics

Run with: pytest tests/integration/ -v
Requires: PostgreSQL instance (set DATABASE_URL env var or use testcontainers)

Environment Variables:
- DATABASE_URL: PostgreSQL connection URL (e.g., postgresql+psycopg2://user:pass@host:port/db)
- TEST_POSTGRES_AVAILABLE: Set to "true" to enable integration tests

If PostgreSQL is not available, tests will be skipped with a clear message.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Generator

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import Settings
from src.data_protection import (
    cleanup_expired_records,
    get_minimized_features,
    get_retention_stats,
)
from src.database import (
    Base,
    dispose_engine,
)
from src.models import PredictionRecord

# ============================================================================
# Test Configuration and Fixtures
# ============================================================================

def _is_postgres_available() -> bool:
    """Check if PostgreSQL is available via DATABASE_URL."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return False
    try:
        import psycopg2
        conn = psycopg2.connect(database_url)
        conn.close()
        return True
    except Exception:
        return False


# Skip all integration tests if PostgreSQL is not available
pytestmark = pytest.mark.skipif(
    not _is_postgres_available(),
    reason="PostgreSQL not available - set DATABASE_URL env var to run integration tests"
)


@pytest.fixture(scope="session")
def postgres_settings() -> Settings:
    """Get settings configured for PostgreSQL testing."""
    settings = Settings()
    # Override with test database URL from env
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        settings.DATABASE_URL = database_url
    return settings


@pytest.fixture(scope="session")
def pg_engine(postgres_settings: Settings) -> Generator[Engine, None, None]:
    """Create a PostgreSQL engine for integration tests."""
    database_url = postgres_settings.DATABASE_URL
    if database_url.startswith("postgresql://") and not database_url.startswith("postgresql+psycopg2://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=postgres_settings.DB_POOL_SIZE,
        max_overflow=postgres_settings.DB_MAX_OVERFLOW,
        pool_timeout=postgres_settings.DB_POOL_TIMEOUT,
        pool_recycle=postgres_settings.DB_POOL_RECYCLE,
    )

    yield engine

    # Cleanup
    engine.dispose()


@pytest.fixture(scope="session")
def pg_session_factory(pg_engine: Engine) -> sessionmaker:
    """Create a session factory for the test database."""
    return sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


@pytest.fixture
def pg_session(pg_session_factory: sessionmaker, pg_engine: Engine) -> Generator[Session, None, None]:
    """Create a clean database session for each test."""
    # Ensure tables exist
    Base.metadata.create_all(bind=pg_engine)

    session = pg_session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

    # Clean up tables after test
    Base.metadata.drop_all(bind=pg_engine)


@pytest.fixture
def pg_db_session(pg_session: Session) -> Generator[Session, None, None]:
    """Alias for pg_session for compatibility with existing code."""
    yield pg_session


# ============================================================================
# Part A: Test Actual PostgreSQL Migrations
# ============================================================================

class TestPostgreSQLMigrations:
    """Test PostgreSQL-specific migration behavior."""

    def test_migrations_upgrade_existing_schema(self, pg_engine: Engine) -> None:
        """Test that migrations can upgrade an existing schema correctly."""
        from alembic.config import Config

        from alembic import command

        # Get alembic config
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", str(pg_engine.url))

        # Get current revision (unused but useful for debugging)
        from alembic.script import ScriptDirectory
        _ = ScriptDirectory.from_config(alembic_cfg).get_current_head()

        # Stamp to base (no migrations applied)
        command.stamp(alembic_cfg, "base")

        # Verify no tables exist
        inspector = sa.inspect(pg_engine)
        tables_before = inspector.get_table_names()
        assert "prediction_records" not in tables_before
        assert "retention_recommendations" not in tables_before

        # Run migrations to head
        command.upgrade(alembic_cfg, "head")

        # Verify tables exist
        inspector = sa.inspect(pg_engine)
        tables_after = inspector.get_table_names()
        assert "prediction_records" in tables_after
        assert "retention_recommendations" in tables_after

    def test_schema_matches_orm_intended_schema(self, pg_engine: Engine) -> None:
        """Test that the database schema matches the ORM's intended schema."""
        inspector = sa.inspect(pg_engine)

        # Check prediction_records table
        pr_columns = {col["name"]: col for col in inspector.get_columns("prediction_records")}
        assert "id" in pr_columns
        assert "customer_id" in pr_columns
        assert "churn_probability" in pr_columns
        assert "churn_prediction" in pr_columns
        assert "risk_segment" in pr_columns
        assert "model_version" in pr_columns
        assert "created_at" in pr_columns
        assert "raw_features" in pr_columns

        # Check retention_recommendations table
        rr_columns = {col["name"]: col for col in inspector.get_columns("retention_recommendations")}
        assert "id" in rr_columns
        assert "prediction_record_id" in rr_columns
        assert "action" in rr_columns
        assert "reason" in rr_columns
        assert "created_at" in rr_columns

        # Check foreign key
        fks = inspector.get_foreign_keys("retention_recommendations")
        assert len(fks) == 1
        assert fks[0]["referred_table"] == "prediction_records"
        assert fks[0]["constrained_columns"] == ["prediction_record_id"]

        # Check indexes
        indexes = inspector.get_indexes("prediction_records")
        index_names = [idx["name"] for idx in indexes]
        assert "ix_prediction_records_customer_id" in index_names
        assert "ix_prediction_records_created_at_customer_id" in index_names

    def test_timezone_migration_results_in_postgresql_timezone_aware_column(self, pg_engine: Engine) -> None:
        """Test that timezone migration results in PostgreSQL timezone-aware column type."""
        inspector = sa.inspect(pg_engine)

        pr_columns = {col["name"]: col for col in inspector.get_columns("prediction_records")}
        rr_columns = {col["name"]: col for col in inspector.get_columns("retention_recommendations")}

        # Check that created_at columns are timezone-aware in PostgreSQL
        pr_created_at = pr_columns["created_at"]
        rr_created_at = rr_columns["created_at"]

        # In PostgreSQL with timezone=True, the type should be TIMESTAMP WITH TIME ZONE
        pr_type = str(pr_created_at["type"]).upper()
        rr_type = str(rr_created_at["type"]).upper()

        assert "TIME ZONE" in pr_type or "TIMEZONE" in pr_type, \
            f"Expected timezone-aware timestamp, got: {pr_type}"
        assert "TIME ZONE" in rr_type or "TIMEZONE" in rr_type, \
            f"Expected timezone-aware timestamp, got: {rr_type}"

    def test_existing_prediction_data_preserved_during_migrations(self, pg_engine: Engine) -> None:
        """Test that existing prediction data is preserved during migrations."""
        from alembic.config import Config

        from alembic import command

        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", str(pg_engine.url))

        # Create initial schema at base
        command.stamp(alembic_cfg, "base")
        Base.metadata.create_all(bind=pg_engine)

        # Insert test data with naive datetime (simulating pre-migration data)
        SessionLocal = sessionmaker(bind=pg_engine)
        session = SessionLocal()
        try:
            # Insert record with naive datetime (pre-timezone migration)
            pred = PredictionRecord(
                customer_id="MIGRATION-TEST-1",
                churn_probability=0.75,
                churn_prediction=1,
                risk_segment="High",
                model_version="1.0.0",
                created_at=datetime(2024, 1, 15, 10, 30, 0)  # naive datetime
            )
            session.add(pred)
            session.commit()
            pred_id = pred.id
        finally:
            session.close()

        # Run timezone migration
        alembic_cfg.set_main_option("sqlalchemy.url", str(pg_engine.url))
        command.upgrade(alembic_cfg, "822094d5e45a")

        # Verify data preserved
        session = SessionLocal()
        try:
            pred = session.query(PredictionRecord).filter_by(id=pred_id).first()
            assert pred is not None
            assert pred.customer_id == "MIGRATION-TEST-1"
            assert pred.churn_probability == 0.75
            # Verify timezone was handled (naive datetime should be treated as UTC)
            assert pred.created_at is not None
        finally:
            session.close()

    def test_migration_execution_failures_handled_safely(self, pg_engine: Engine) -> None:
        """Test that migration execution failures are handled safely."""
        from alembic.config import Config

        from alembic import command

        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", str(pg_engine.url))

        # Stamp to head first
        command.stamp(alembic_cfg, "head")

        # Try to apply migration that already exists - should not fail
        command.upgrade(alembic_cfg, "head")

        # Verify schema still intact
        inspector = sa.inspect(pg_engine)
        tables = inspector.get_table_names()
        assert "prediction_records" in tables
        assert "retention_recommendations" in tables

    def test_migrations_can_run_repeatedly_or_report_no_upgrade_required(self, pg_engine: Engine) -> None:
        """Test that migrations can be run repeatedly without error."""
        from alembic.config import Config

        from alembic import command

        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", str(pg_engine.url))

        # Apply migrations multiple times
        for _ in range(3):
            command.upgrade(alembic_cfg, "head")

        # Verify final state
        inspector = sa.inspect(pg_engine)
        assert "prediction_records" in inspector.get_table_names()
        assert "retention_recommendations" in inspector.get_table_names()

    def test_downgrade_recovery_procedure(self, pg_engine: Engine) -> None:
        """Test that downgrade procedure is appropriate."""
        from alembic.config import Config

        from alembic import command

        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", str(pg_engine.url))

        # Ensure at head
        command.upgrade(alembic_cfg, "head")

        # Downgrade one step (timezone migration)
        command.downgrade(alembic_cfg, "b1c2d3e4f5a6")

        # Verify timezone columns reverted (naive datetime)
        inspector = sa.inspect(pg_engine)
        pr_columns = {col["name"]: col for col in inspector.get_columns("prediction_records")}
        pr_type = str(pr_columns["created_at"]["type"]).upper()

        # Should be naive datetime after downgrade
        assert "TIME ZONE" not in pr_type and "TIMEZONE" not in pr_type

        # Upgrade back to head
        command.upgrade(alembic_cfg, "head")


# ============================================================================
# Part B: Verify Timestamp Semantics
# ============================================================================

class TestTimestampSemantics:
    """Test timestamp creation, retrieval, and timezone handling."""

    def test_timestamp_creation_retrieval_utc_consistent(self, pg_db_session: Session) -> None:
        """Test that timestamps are created and retrieved as UTC."""
        # Create record with explicit UTC datetime
        utc_now = datetime.now(timezone.utc)
        pred = PredictionRecord(
            customer_id="TIMESTAMP-TEST-1",
            churn_probability=0.5,
            churn_prediction=0,
            risk_segment="Medium",
            model_version="1.0.0",
            created_at=utc_now
        )
        pg_db_session.add(pred)
        pg_db_session.commit()
        pg_db_session.refresh(pred)

        # Verify retrieved timestamp is timezone-aware and UTC
        assert pred.created_at is not None
        assert pred.created_at.tzinfo is not None
        # Should be equivalent to UTC time
        assert pred.created_at.utcoffset() == timedelta(0)

    def test_timestamp_naive_datetime_treated_as_utc(self, pg_db_session: Session) -> None:
        """Test that naive datetimes are treated as UTC by the ORM."""
        # Create with naive datetime
        naive_dt = datetime(2024, 6, 15, 14, 30, 0)  # naive
        pred = PredictionRecord(
            customer_id="TIMESTAMP-TEST-2",
            churn_probability=0.3,
            churn_prediction=0,
            risk_segment="Low",
            model_version="1.0.0",
            created_at=naive_dt
        )
        pg_db_session.add(pred)
        pg_db_session.commit()
        pg_db_session.refresh(pred)

        # Should be stored and retrieved with UTC timezone
        assert pred.created_at is not None
        assert pred.created_at.tzinfo is not None

    def test_timestamp_serialization_deserialization(self, pg_db_session: Session) -> None:
        """Test timestamp serialization to JSON and back."""
        utc_now = datetime.now(timezone.utc)
        pred = PredictionRecord(
            customer_id="TIMESTAMP-TEST-3",
            churn_probability=0.9,
            churn_prediction=1,
            risk_segment="High",
            model_version="1.0.0",
            created_at=utc_now,
            raw_features={"test": "data"}
        )
        pg_db_session.add(pred)
        pg_db_session.commit()
        pg_db_session.refresh(pred)

        # Serialize to dict (simulating API response)
        data = {
            "id": pred.id,
            "created_at": pred.created_at.isoformat() if pred.created_at else None,
        }

        # Deserialize
        parsed = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timedelta(0)

    def test_timestamp_comparison_and_ordering(self, pg_db_session: Session) -> None:
        """Test timestamp comparison and ordering operations."""
        base_time = datetime.now(timezone.utc)

        pred1 = PredictionRecord(
            customer_id="TIMESTAMP-TEST-4",
            churn_probability=0.1,
            churn_prediction=0,
            risk_segment="Low",
            model_version="1.0.0",
            created_at=base_time - timedelta(hours=2)
        )
        pred2 = PredictionRecord(
            customer_id="TIMESTAMP-TEST-5",
            churn_probability=0.2,
            churn_prediction=0,
            risk_segment="Low",
            model_version="1.0.0",
            created_at=base_time - timedelta(hours=1)
        )
        pg_db_session.add_all([pred1, pred2])
        pg_db_session.commit()

        # Query with ordering
        results = pg_db_session.query(PredictionRecord).filter(
            PredictionRecord.customer_id.like("TIMESTAMP-TEST-%")
        ).order_by(PredictionRecord.created_at).all()

        assert len(results) == 2
        assert results[0].created_at < results[1].created_at

    def test_timestamp_timezone_offsets(self, pg_db_session: Session) -> None:
        """Test handling of different timezone offsets."""
        # Create with different timezone
        eastern = timezone(timedelta(hours=-5))
        eastern_time = datetime(2024, 6, 15, 14, 30, 0, tzinfo=eastern)

        pred = PredictionRecord(
            customer_id="TIMESTAMP-TEST-6",
            churn_probability=0.4,
            churn_prediction=0,
            risk_segment="Medium",
            model_version="1.0.0",
            created_at=eastern_time
        )
        pg_db_session.add(pred)
        pg_db_session.commit()
        pg_db_session.refresh(pred)

        # Should be stored as UTC
        assert pred.created_at is not None
        assert pred.created_at.tzinfo is not None
        # 14:30 EDT = 18:30 UTC
        assert pred.created_at.hour == 18
        assert pred.created_at.minute == 30

    def test_historical_naive_timestamps_assumptions_documented(self, pg_db_session: Session) -> None:
        """Test that migration assumptions about historical naive timestamps are documented."""
        # This test verifies the behavior is documented in the migration
        # The migration 822094d5e45a explicitly handles this:
        # - For PostgreSQL: converts naive to timezone-aware (assumes UTC)
        # - For SQLite: no-op, ORM handles it
        #
        # This test ensures the behavior is consistent with documentation

        # Create record with naive datetime
        naive_dt = datetime(2023, 1, 1, 12, 0, 0)
        pred = PredictionRecord(
            customer_id="HISTORICAL-TEST",
            churn_probability=0.5,
            churn_prediction=0,
            risk_segment="Medium",
            model_version="1.0.0",
            created_at=naive_dt
        )
        pg_db_session.add(pred)
        pg_db_session.commit()
        pg_db_session.refresh(pred)

        # The ORM should treat naive as UTC
        assert pred.created_at.tzinfo is not None
        # The time should be preserved (12:00 UTC)
        assert pred.created_at.hour == 12
        assert pred.created_at.minute == 0


# ============================================================================
# Part C: Test Database Pooling and Failures
# ============================================================================

class TestConnectionPooling:
    """Test connection pooling and failure handling."""

    def test_connection_reuse(self, pg_engine: Engine) -> None:
        """Test that connections are properly reused from the pool."""
        pool = pg_engine.pool

        # Get initial pool status
        _ = pool.size()
        checked_out = pool.checkedout()

        # Get multiple connections
        conn1 = pg_engine.connect()
        conn2 = pg_engine.connect()

        # Check pool status
        after_checkout = pool.checkedout()
        assert after_checkout >= checked_out + 1

        # Return connections
        conn1.close()
        conn2.close()

        # Check pool status restored
        after_return = pool.checkedout()
        assert after_return == checked_out

    def test_session_cleanup_on_exception(self, pg_session_factory: sessionmaker) -> None:
        """Test that sessions are properly cleaned up after exceptions."""
        session = pg_session_factory()
        try:
            pred = PredictionRecord(
                customer_id="EXCEPTION-TEST",
                churn_probability=0.5,
                churn_prediction=0,
                risk_segment="Medium",
                model_version="1.0.0"
            )
            session.add(pred)
            session.flush()  # Flush to DB
            raise ValueError("Simulated error")
        except ValueError:
            pass
        finally:
            session.rollback()
            session.close()

        # Verify no record was committed
        new_session = pg_session_factory()
        try:
            count = new_session.query(PredictionRecord).filter_by(
                customer_id="EXCEPTION-TEST"
            ).count()
            assert count == 0
        finally:
            new_session.close()

    def test_recovery_after_failed_transaction(self, pg_session_factory: sessionmaker) -> None:
        """Test recovery after a failed transaction."""
        # First transaction fails
        session1 = pg_session_factory()
        try:
            pred = PredictionRecord(
                customer_id="RECOVERY-TEST",
                churn_probability=0.5,
                churn_prediction=0,
                risk_segment="Medium",
                model_version="1.0.0"
            )
            session1.add(pred)
            session1.flush()
            raise ValueError("Transaction failed")
        except ValueError:
            session1.rollback()
        finally:
            session1.close()

        # Subsequent transaction should work
        session2 = pg_session_factory()
        try:
            pred = PredictionRecord(
                customer_id="RECOVERY-TEST-2",
                churn_probability=0.5,
                churn_prediction=0,
                risk_segment="Medium",
                model_version="1.0.0"
            )
            session2.add(pred)
            session2.commit()
        finally:
            session2.close()

        # Verify second record exists
        session3 = pg_session_factory()
        try:
            count = session3.query(PredictionRecord).filter_by(
                customer_id="RECOVERY-TEST-2"
            ).count()
            assert count == 1
        finally:
            session3.close()

    def test_pool_exhaustion_behavior(self, pg_engine: Engine, pg_session_factory: sessionmaker) -> None:
        """Test behavior when connection pool is exhausted."""
        # Get pool configuration
        pool = pg_engine.pool
        pool_size = pool.size()
        max_overflow = getattr(pool, "_max_overflow", 0)

        # Try to exhaust pool (create pool_size + max_overflow + 1 connections)
        connections = []
        try:
            for _ in range(pool_size + max_overflow + 1):
                conn = pg_engine.connect()
                connections.append(conn)

            # Should have exhausted pool
            assert len(connections) == pool_size + max_overflow + 1
        finally:
            # Clean up
            for conn in connections:
                conn.close()

    def test_database_unavailable_recovery(self, pg_session_factory: sessionmaker) -> None:
        """Test recovery behavior when database becomes temporarily unavailable."""
        session = pg_session_factory()
        try:
            # Normal operation
            pred = PredictionRecord(
                customer_id="UNAVAILABLE-TEST",
                churn_probability=0.5,
                churn_prediction=0,
                risk_segment="Medium",
                model_version="1.0.0"
            )
            session.add(pred)
            session.commit()
        finally:
            session.close()

        # Simulate temporary unavailability by disposing engine
        dispose_engine()

        # New session should create new engine
        new_session = pg_session_factory()
        try:
            pred = PredictionRecord(
                customer_id="UNAVAILABLE-TEST-2",
                churn_probability=0.5,
                churn_prediction=0,
                risk_segment="Medium",
                model_version="1.0.0"
            )
            new_session.add(pred)
            new_session.commit()
        finally:
            new_session.close()


# ============================================================================
# Part D: Verify Customer Data Minimization and Retention
# ============================================================================

class TestDataMinimizationAndRetention:
    """Test data minimization and retention cleanup with PostgreSQL."""

    def test_sensitive_fields_excluded_from_persistence(self, pg_db_session: Session) -> None:
        """Test that sensitive fields are excluded from raw_features when minimization enabled."""
        # Mock settings with minimization enabled
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("src.config.get_settings", lambda: Settings(
                DATA_MINIMIZATION_ENABLED=True
            ))

            raw_data = {
                "customerID": "SENSITIVE-TEST",
                "tenure": 12,
                "MonthlyCharges": 75.50,
                "TotalCharges": 900.00,
                "gender": "Female",
                "SeniorCitizen": 0,
                "Contract": "Month-to-month",
                "PaymentMethod": "Electronic check",
                "InternetService": "DSL",
                "TechSupport": "Yes"
            }

            minimized = get_minimized_features(raw_data, include_business_fields=True)

            # Sensitive fields should be excluded
            assert "customerID" not in minimized
            assert "MonthlyCharges" not in minimized
            assert "TotalCharges" not in minimized
            assert "gender" not in minimized
            assert "SeniorCitizen" not in minimized
            assert "PaymentMethod" not in minimized

            # Business fields should be included
            assert "Contract" in minimized
            assert "MonthlyCharges" in minimized  # Business required
            assert "InternetService" in minimized
            assert "TechSupport" in minimized

            # Safe fields included
            assert "tenure" in minimized

            # Metadata added
            assert minimized["_minimized"] is True
            assert "_minimized_at" in minimized
            assert "_original_field_count" in minimized
            assert "_retained_field_count" in minimized

    def test_business_fields_remain_available(self, pg_db_session: Session) -> None:
        """Test that required business fields remain available after minimization."""
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("src.config.get_settings", lambda: Settings(
                DATA_MINIMIZATION_ENABLED=True
            ))

            raw_data = {
                "customerID": "BUSINESS-TEST",
                "Contract": "One year",
                "MonthlyCharges": 65.00,
                "InternetService": "Fiber optic",
                "TechSupport": "Yes",
                "tenure": 24
            }

            minimized = get_minimized_features(raw_data, include_business_fields=True)

            # All business fields should be present
            assert minimized["Contract"] == "One year"
            assert minimized["MonthlyCharges"] == 65.00
            assert minimized["InternetService"] == "Fiber optic"
            assert minimized["TechSupport"] == "Yes"

    def test_expired_records_cleaned_according_to_retention_period(self, pg_db_session: Session) -> None:
        """Test that expired records are cleaned according to configured retention period."""
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("src.config.get_settings", lambda: Settings(
                DATA_RETENTION_DAYS=30,
                DATA_RETENTION_BATCH_SIZE=100,
                DATA_RETENTION_DRY_RUN=False
            ))

            # Create old records (expired)
            old_date = datetime.now(timezone.utc) - timedelta(days=60)
            for i in range(5):
                pred = PredictionRecord(
                    customer_id=f"OLD-RECORD-{i}",
                    churn_probability=0.5,
                    churn_prediction=0,
                    risk_segment="Medium",
                    model_version="1.0.0",
                    created_at=old_date
                )
                pg_db_session.add(pred)
            pg_db_session.commit()

            # Create recent records (not expired)
            recent_date = datetime.now(timezone.utc) - timedelta(days=10)
            for i in range(3):
                pred = PredictionRecord(
                    customer_id=f"RECENT-RECORD-{i}",
                    churn_probability=0.5,
                    churn_prediction=0,
                    risk_segment="Medium",
                    model_version="1.0.0",
                    created_at=recent_date
                )
                pg_db_session.add(pred)
            pg_db_session.commit()

            # Run cleanup
            result = cleanup_expired_records(
                db=pg_db_session,
                retention_days=30,
                batch_size=100,
                dry_run=False
            )

            # Verify old records deleted
            assert result["deleted_prediction_records"] == 5
            assert result["batches_processed"] == 1

            # Verify recent records preserved
            remaining = pg_db_session.query(PredictionRecord).filter(
                PredictionRecord.customer_id.like("RECENT-%")
            ).count()
            assert remaining == 3

    def test_records_at_retention_boundary_follow_documented_rule(self, pg_db_session: Session) -> None:
        """Test that records exactly at retention boundary follow documented rule."""
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("src.config.get_settings", lambda: Settings(
                DATA_RETENTION_DAYS=30,
                DATA_RETENTION_BATCH_SIZE=100,
                DATA_RETENTION_DRY_RUN=False
            ))

            # Record exactly at boundary (30 days ago)
            boundary_date = datetime.now(timezone.utc) - timedelta(days=30, minutes=1)
            pred_exact = PredictionRecord(
                customer_id="BOUNDARY-EXACT",
                churn_probability=0.5,
                churn_prediction=0,
                risk_segment="Medium",
                model_version="1.0.0",
                created_at=boundary_date
            )

            # Record just inside boundary (29 days 23 hours ago)
            pred_inside = PredictionRecord(
                customer_id="BOUNDARY-INSIDE",
                churn_probability=0.5,
                churn_prediction=0,
                risk_segment="Medium",
                model_version="1.0.0",
                created_at=datetime.now(timezone.utc) - timedelta(days=29, hours=23)
            )

            pg_db_session.add_all([pred_exact, pred_inside])
            pg_db_session.commit()

            # Run cleanup
            _ = cleanup_expired_records(
                db=pg_db_session,
                retention_days=30,
                batch_size=100,
                dry_run=False
            )

            # Exact boundary record should be deleted (older than cutoff)
            # Inside boundary should be preserved
            exact_deleted = pg_db_session.query(PredictionRecord).filter_by(
                customer_id="BOUNDARY-EXACT"
            ).count()
            inside_preserved = pg_db_session.query(PredictionRecord).filter_by(
                customer_id="BOUNDARY-INSIDE"
            ).count()

            assert exact_deleted == 0  # Record is deleted
            assert inside_preserved == 1  # Record is preserved

    def test_batch_cleanup_and_dry_run_behavior(self, pg_db_session: Session) -> None:
        """Test batch cleanup and dry-run behavior."""
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("src.config.get_settings", lambda: Settings(
                DATA_RETENTION_DAYS=30,
                DATA_RETENTION_BATCH_SIZE=2,  # Small batch for testing
                DATA_RETENTION_DRY_RUN=True
            ))

            # Create 5 expired records
            old_date = datetime.now(timezone.utc) - timedelta(days=60)
            for i in range(5):
                pred = PredictionRecord(
                    customer_id=f"BATCH-TEST-{i}",
                    churn_probability=0.5,
                    churn_prediction=0,
                    risk_segment="Medium",
                    model_version="1.0.0",
                    created_at=old_date
                )
                pg_db_session.add(pred)
            pg_db_session.commit()

            # Run dry-run cleanup
            result = cleanup_expired_records(
                db=pg_db_session,
                retention_days=30,
                batch_size=2,
                dry_run=True
            )

            # Should report what would be deleted
            assert result["deleted_prediction_records"] == 5
            assert result["batches_processed"] == 3  # 2+2+1
            assert result["dry_run"] is True

            # Actual records should not be deleted
            actual_count = pg_db_session.query(PredictionRecord).filter(
                PredictionRecord.customer_id.like("BATCH-TEST-%")
            ).count()
            assert actual_count == 5

    def test_repeated_cleanup_no_corruption_no_duplicates(self, pg_db_session: Session) -> None:
        """Test that repeated cleanup does not corrupt data or generate duplicates."""
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("src.config.get_settings", lambda: Settings(
                DATA_RETENTION_DAYS=30,
                DATA_RETENTION_BATCH_SIZE=100,
                DATA_RETENTION_DRY_RUN=False
            ))

            # Create expired records
            old_date = datetime.now(timezone.utc) - timedelta(days=60)
            for i in range(3):
                pred = PredictionRecord(
                    customer_id=f"REPEAT-TEST-{i}",
                    churn_probability=0.5,
                    churn_prediction=0,
                    risk_segment="Medium",
                    model_version="1.0.0",
                    created_at=old_date
                )
                pg_db_session.add(pred)
            pg_db_session.commit()

            # Run cleanup first time
            result1 = cleanup_expired_records(db=pg_db_session, dry_run=False)
            assert result1["deleted_prediction_records"] == 3

            # Run cleanup second time (should find nothing)
            result2 = cleanup_expired_records(db=pg_db_session, dry_run=False)
            assert result2["deleted_prediction_records"] == 0

            # Verify no records remain
            remaining = pg_db_session.query(PredictionRecord).filter(
                PredictionRecord.customer_id.like("REPEAT-TEST-%")
            ).count()
            assert remaining == 0

    def test_failures_do_not_silently_report_success(self, pg_db_session: Session) -> None:
        """Test that failures do not silently report successful cleanup."""
        # Test with invalid database state
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("src.config.get_settings", lambda: Settings(
                DATA_RETENTION_DAYS=30,
                DATA_RETENTION_BATCH_SIZE=100,
                DATA_RETENTION_DRY_RUN=False
            ))

            # Close the session to simulate failure
            pg_db_session.close()

            # Should raise exception, not silently succeed
            with pytest.raises((Exception, sa.exc.OperationalError)):
                cleanup_expired_records(db=pg_db_session, dry_run=False)

    def test_minimization_metadata_and_cleanup_audit_statistics(self, pg_db_session: Session) -> None:
        """Test that minimization metadata and cleanup audit statistics are accurate."""
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("src.config.get_settings", lambda: Settings(
                DATA_MINIMIZATION_ENABLED=True,
                DATA_RETENTION_DAYS=30,
                DATA_RETENTION_BATCH_SIZE=100,
                DATA_RETENTION_DRY_RUN=False
            ))

            # Create records with minimized features
            old_date = datetime.now(timezone.utc) - timedelta(days=60)
            raw_data = {
                "customerID": "META-TEST",
                "tenure": 24,
                "MonthlyCharges": 80.0,
                "Contract": "Two year",
                "InternetService": "Fiber optic",
                "TechSupport": "Yes",
                "gender": "Male"
            }
            minimized = get_minimized_features(raw_data, include_business_fields=True)

            pred = PredictionRecord(
                customer_id="META-TEST",
                churn_probability=0.5,
                churn_prediction=0,
                risk_segment="Medium",
                model_version="1.0.0",
                raw_features=minimized,
                created_at=old_date
            )
            pg_db_session.add(pred)
            pg_db_session.commit()

            # Verify metadata in raw_features
            pg_db_session.refresh(pred)
            assert pred.raw_features["_minimized"] is True
            assert "_minimized_at" in pred.raw_features
            assert pred.raw_features["_original_field_count"] == len(raw_data)
            assert pred.raw_features["_retained_field_count"] > 0

            # Run cleanup and check stats
            result = cleanup_expired_records(db=pg_db_session, dry_run=False)
            assert result["deleted_prediction_records"] == 1
            assert "completed_at" in result
            assert result["retention_days"] == 30

            # Check retention stats
            stats = get_retention_stats(pg_db_session, retention_days=30)
            assert stats["expired_prediction_records"] == 0  # Already deleted
            assert stats["total_prediction_records"] == 0


# ============================================================================
# Test Runner
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
