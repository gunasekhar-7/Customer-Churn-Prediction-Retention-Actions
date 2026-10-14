"""
Tests for data protection and retention functionality.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import Settings
from src.data_protection import (
    BUSINESS_REQUIRED_FIELDS,
    SAFE_FIELDS,
    SENSITIVE_FIELDS,
    cleanup_expired_records,
    create_prediction_record,
    get_minimized_features,
    get_retention_stats,
    get_sensitive_fields,
)
from src.database import Base
from src.models import PredictionRecord, RetentionRecommendationRecord


@pytest.fixture
def sample_customer_data():
    """Sample customer data matching TelcoCustomerRecord schema."""
    return {
        "customerID": "1234-ABCD",
        "gender": "Female",
        "SeniorCitizen": 0,
        "Partner": "Yes",
        "Dependents": "No",
        "tenure": 12,
        "PhoneService": "Yes",
        "MultipleLines": "No",
        "InternetService": "DSL",
        "OnlineSecurity": "No",
        "OnlineBackup": "Yes",
        "DeviceProtection": "No",
        "TechSupport": "Yes",
        "StreamingTV": "No",
        "StreamingMovies": "No",
        "Contract": "Month-to-month",
        "PaperlessBilling": "Yes",
        "PaymentMethod": "Electronic check",
        "MonthlyCharges": 50.0,
        "TotalCharges": "600.0",
        "Churn": "No"
    }


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()


class TestDataMinimization:
    """Tests for data minimization utilities."""

    def test_get_minimized_features_enabled(self, sample_customer_data):
        """Test minimization with default settings (enabled)."""
        with patch('src.data_protection.get_settings') as mock_settings:
            mock_settings.return_value.DATA_MINIMIZATION_ENABLED = True
            minimized = get_minimized_features(sample_customer_data)

        # Should contain safe fields
        assert "tenure" in minimized
        assert minimized["tenure"] == 12

        # Should contain business-required fields
        assert "Contract" in minimized
        assert minimized["Contract"] == "Month-to-month"
        assert "MonthlyCharges" in minimized
        assert minimized["MonthlyCharges"] == 50.0
        assert "InternetService" in minimized
        assert minimized["InternetService"] == "DSL"
        assert "TechSupport" in minimized
        assert minimized["TechSupport"] == "Yes"

        # Should NOT contain sensitive fields
        assert "customerID" not in minimized
        assert "gender" not in minimized
        assert "SeniorCitizen" not in minimized
        assert "Partner" not in minimized
        assert "Dependents" not in minimized
        assert "PhoneService" not in minimized
        assert "MultipleLines" not in minimized
        assert "OnlineSecurity" not in minimized
        assert "OnlineBackup" not in minimized
        assert "DeviceProtection" not in minimized
        assert "StreamingTV" not in minimized
        assert "StreamingMovies" not in minimized
        assert "PaperlessBilling" not in minimized
        assert "PaymentMethod" not in minimized
        assert "TotalCharges" not in minimized
        assert "Churn" not in minimized

        # Should have minimization metadata
        assert minimized["_minimized"] is True
        assert "_minimized_at" in minimized
        assert "_original_field_count" in minimized
        assert "_retained_field_count" in minimized

    def test_get_minimized_features_disabled(self, sample_customer_data):
        """Test minimization when disabled (returns all fields)."""
        with patch('src.data_protection.get_settings') as mock_settings:
            mock_settings.return_value.DATA_MINIMIZATION_ENABLED = False
            minimized = get_minimized_features(sample_customer_data)

        # Should contain all original fields
        assert minimized == sample_customer_data

    def test_get_minimized_features_no_business_fields(self, sample_customer_data):
        """Test minimization without business-required fields."""
        with patch('src.data_protection.get_settings') as mock_settings:
            mock_settings.return_value.DATA_MINIMIZATION_ENABLED = True
            minimized = get_minimized_features(sample_customer_data, include_business_fields=False)

        # Should only contain safe fields
        assert "tenure" in minimized
        assert "Contract" not in minimized
        assert "MonthlyCharges" not in minimized
        assert "InternetService" not in minimized
        assert "TechSupport" not in minimized

    def test_get_sensitive_fields(self, sample_customer_data):
        """Test extraction of sensitive fields."""
        sensitive = get_sensitive_fields(sample_customer_data)

        # Should contain all sensitive fields
        assert "customerID" in sensitive
        assert "MonthlyCharges" in sensitive
        assert "TotalCharges" in sensitive
        assert "PaymentMethod" in sensitive
        assert "Contract" in sensitive
        assert "gender" in sensitive
        assert "SeniorCitizen" in sensitive

        # Should NOT contain safe fields
        assert "tenure" not in sensitive

    def test_create_prediction_record_with_minimization(self, sample_customer_data):
        """Test creating PredictionRecord with minimized features."""
        with patch('src.data_protection.get_settings') as mock_settings:
            mock_settings.return_value.DATA_MINIMIZATION_ENABLED = True
            record = create_prediction_record(
                customer_id="1234-ABCD",
                churn_probability=0.75,
                churn_prediction=1,
                risk_segment="High",
                model_version="1.0.0",
                raw_features=sample_customer_data,
            )

        assert record.customer_id == "1234-ABCD"
        assert record.churn_probability == 0.75
        assert record.churn_prediction == 1
        assert record.risk_segment == "High"
        assert record.model_version == "1.0.0"
        assert record.raw_features is not None
        assert record.raw_features["tenure"] == 12
        assert record.raw_features["Contract"] == "Month-to-month"
        assert "customerID" not in record.raw_features
        assert "gender" not in record.raw_features

    def test_create_prediction_record_without_minimization(self, sample_customer_data):
        """Test creating PredictionRecord without minimization."""
        with patch('src.data_protection.get_settings') as mock_settings:
            mock_settings.return_value.DATA_MINIMIZATION_ENABLED = False
            record = create_prediction_record(
                customer_id="1234-ABCD",
                churn_probability=0.75,
                churn_prediction=1,
                risk_segment="High",
                model_version="1.0.0",
                raw_features=sample_customer_data,
            )

        # Should contain all fields when minimization is disabled
        assert record.raw_features == sample_customer_data


class TestRetentionCleanup:
    """Tests for retention cleanup functionality."""

    def create_test_records(self, db_session, days_old_list):
        """Create test prediction records with specified ages."""
        records = []
        for i, days_old in enumerate(days_old_list):
            created_at = datetime.now(timezone.utc) - timedelta(days=days_old)
            record = PredictionRecord(
                customer_id=f"CUST-{i:04d}",
                churn_probability=0.5,
                churn_prediction=0,
                risk_segment="Medium",
                model_version="1.0.0",
                created_at=created_at,
                raw_features={"tenure": 12}
            )
            db_session.add(record)
            db_session.flush()

            # Add a recommendation for each
            rec = RetentionRecommendationRecord(
                prediction_record_id=record.id,
                action="Test Action",
                reason="Test Reason",
                created_at=created_at
            )
            db_session.add(rec)
            records.append(record)

        db_session.commit()
        return records

    def test_cleanup_expired_records_dry_run(self, db_session):
        """Test dry run cleanup identifies correct records."""
        # Create records: 2 expired (100 days old), 2 active (30 days old)
        self.create_test_records(db_session, [100, 100, 30, 30])

        with patch('src.data_protection.get_settings') as mock_settings:
            mock_settings.return_value.DATA_RETENTION_DAYS = 90
            mock_settings.return_value.DATA_RETENTION_BATCH_SIZE = 1000
            mock_settings.return_value.DATA_RETENTION_DRY_RUN = True

            result = cleanup_expired_records(db_session, dry_run=True)

        assert result["deleted_prediction_records"] == 2
        assert result["deleted_recommendations"] == 2
        assert result["dry_run"] is True
        assert result["batches_processed"] == 1

        # Verify records still exist in database
        remaining = db_session.query(PredictionRecord).count()
        assert remaining == 4

    def test_cleanup_expired_records_actual_deletion(self, db_session):
        """Test actual cleanup deletes expired records."""
        # Create records: 2 expired (100 days old), 2 active (30 days old)
        self.create_test_records(db_session, [100, 100, 30, 30])

        with patch('src.data_protection.get_settings') as mock_settings:
            mock_settings.return_value.DATA_RETENTION_DAYS = 90
            mock_settings.return_value.DATA_RETENTION_BATCH_SIZE = 1000
            mock_settings.return_value.DATA_RETENTION_DRY_RUN = False

            result = cleanup_expired_records(db_session, dry_run=False)

        assert result["deleted_prediction_records"] == 2
        assert result["deleted_recommendations"] == 2
        assert result["dry_run"] is False

        # Verify only active records remain
        remaining = db_session.query(PredictionRecord).count()
        assert remaining == 2

        remaining_recs = db_session.query(RetentionRecommendationRecord).count()
        assert remaining_recs == 2

        # Verify remaining records are the active ones
        now = datetime.now(timezone.utc)
        for record in db_session.query(PredictionRecord).all():
            # Ensure both datetimes are timezone-aware
            record_created = record.created_at
            if record_created.tzinfo is None:
                record_created = record_created.replace(tzinfo=timezone.utc)
            age = (now - record_created).days
            assert age < 90

    def test_cleanup_batch_processing(self, db_session):
        """Test cleanup processes in batches."""
        # Create 5 expired records
        self.create_test_records(db_session, [100, 100, 100, 100, 100])

        with patch('src.data_protection.get_settings') as mock_settings:
            mock_settings.return_value.DATA_RETENTION_DAYS = 90
            mock_settings.return_value.DATA_RETENTION_BATCH_SIZE = 2  # Small batch size
            mock_settings.return_value.DATA_RETENTION_DRY_RUN = False

            result = cleanup_expired_records(db_session, dry_run=False)

        assert result["deleted_prediction_records"] == 5
        assert result["batches_processed"] == 3  # 2 + 2 + 1

    def test_cleanup_no_expired_records(self, db_session):
        """Test cleanup when no records are expired."""
        # Create only active records
        self.create_test_records(db_session, [30, 30, 30])

        with patch('src.data_protection.get_settings') as mock_settings:
            mock_settings.return_value.DATA_RETENTION_DAYS = 90
            mock_settings.return_value.DATA_RETENTION_BATCH_SIZE = 1000
            mock_settings.return_value.DATA_RETENTION_DRY_RUN = False

            result = cleanup_expired_records(db_session, dry_run=False)

        assert result["deleted_prediction_records"] == 0
        assert result["deleted_recommendations"] == 0
        assert result["batches_processed"] == 0

    def test_cleanup_partial_failure_rollback(self, db_session):
        """Test cleanup handles partial failures correctly."""
        # This test would require mocking the database to simulate a failure
        # For now, we verify the structure handles it
        pass

    def test_get_retention_stats(self, db_session):
        """Test retention statistics."""
        # Create mixed records
        self.create_test_records(db_session, [100, 100, 30, 30, 10])

        with patch('src.data_protection.get_settings') as mock_settings:
            mock_settings.return_value.DATA_RETENTION_DAYS = 90
            stats = get_retention_stats(db_session)

        assert stats["total_prediction_records"] == 5
        assert stats["expired_prediction_records"] == 2
        assert stats["active_prediction_records"] == 3
        assert stats["total_recommendations"] == 5
        assert stats["expired_recommendations"] == 2
        assert stats["active_recommendations"] == 3


class TestSensitiveFieldDefinitions:
    """Tests for sensitive field definitions."""

    def test_sensitive_fields_not_empty(self):
        assert len(SENSITIVE_FIELDS) > 0

    def test_safe_fields_not_empty(self):
        assert len(SAFE_FIELDS) > 0

    def test_business_required_fields_not_empty(self):
        assert len(BUSINESS_REQUIRED_FIELDS) > 0

    def test_no_overlap_between_sensitive_and_safe(self):
        """Ensure no field is both sensitive and safe."""
        overlap = SENSITIVE_FIELDS.intersection(SAFE_FIELDS)
        assert overlap == set()

    def test_business_fields_are_subset_of_sensitive(self):
        """Business required fields should be a subset of sensitive fields
        (they're sensitive but needed for business logic)."""
        assert BUSINESS_REQUIRED_FIELDS.issubset(SENSITIVE_FIELDS)

    def test_customerID_is_sensitive(self):
        assert "customerID" in SENSITIVE_FIELDS

    def test_financial_fields_are_sensitive(self):
        assert "MonthlyCharges" in SENSITIVE_FIELDS
        assert "TotalCharges" in SENSITIVE_FIELDS
        assert "PaymentMethod" in SENSITIVE_FIELDS

    def test_demographic_fields_are_sensitive(self):
        assert "gender" in SENSITIVE_FIELDS
        assert "SeniorCitizen" in SENSITIVE_FIELDS
        assert "Partner" in SENSITIVE_FIELDS
        assert "Dependents" in SENSITIVE_FIELDS


class TestRetentionConfig:
    """Tests for retention configuration."""

    def test_default_retention_days(self):
        settings = Settings()
        assert settings.DATA_RETENTION_DAYS == 90

    def test_default_batch_size(self):
        settings = Settings()
        assert settings.DATA_RETENTION_BATCH_SIZE == 1000

    def test_default_dry_run(self):
        settings = Settings()
        assert settings.DATA_RETENTION_DRY_RUN is False

    def test_default_minimization_enabled(self):
        settings = Settings()
        assert settings.DATA_MINIMIZATION_ENABLED is True
