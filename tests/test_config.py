import os
from unittest.mock import patch

import pytest

from src.config import Settings, get_settings


class TestSettings:
    def test_default_values(self):
        """Test default configuration values."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.API_HOST == "0.0.0.0"
            assert settings.API_PORT == 8000
            assert settings.API_WORKERS == 2
            assert settings.DB_POOL_SIZE == 5
            assert settings.DB_MAX_OVERFLOW == 10
            assert settings.DB_POOL_TIMEOUT == 30
            assert settings.DB_POOL_RECYCLE == 1800
            assert settings.DB_POOL_PRE_PING is True
            assert settings.LOG_LEVEL == "INFO"
            assert settings.LOG_FORMAT == "json"
            assert settings.ENVIRONMENT == "development"
            assert settings.UVICORN_KEEP_ALIVE_TIMEOUT == 75
            assert settings.UVICORN_WORKER_TIMEOUT == 120
            assert settings.UVICORN_LIMIT_CONCURRENCY == 1000
            assert settings.UVICORN_BACKLOG == 2048

    def test_database_url_validation(self):
        """Test database URL validation and driver correction."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost/db"}, clear=True):
            settings = Settings()
            assert settings.DATABASE_URL == "postgresql+psycopg2://user:pass@localhost/db"

    def test_database_url_already_correct(self):
        """Test database URL with correct driver is not modified."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql+psycopg2://user:pass@localhost/db"}, clear=True):
            settings = Settings()
            assert settings.DATABASE_URL == "postgresql+psycopg2://user:pass@localhost/db"

    def test_environment_validation(self):
        """Test environment validation."""
        with patch.dict(os.environ, {"ENVIRONMENT": "staging"}, clear=True):
            settings = Settings()
            assert settings.ENVIRONMENT == "staging"

    def test_environment_case_insensitive(self):
        """Test environment validation is case insensitive."""
        with patch.dict(os.environ, {"ENVIRONMENT": "PRODUCTION"}, clear=True):
            settings = Settings()
            assert settings.ENVIRONMENT == "production"

    def test_invalid_environment(self):
        """Test invalid environment raises error."""
        with patch.dict(os.environ, {"ENVIRONMENT": "invalid"}, clear=True):
            with pytest.raises(ValueError):
                Settings()

    def test_cors_origins_parsing(self):
        """Test CORS origins parsing."""
        with patch.dict(os.environ, {"CORS_ORIGINS": "http://a.com, http://b.com ,http://c.com"}, clear=True):
            settings = Settings()
            assert settings.CORS_ORIGINS == ["http://a.com", "http://b.com", "http://c.com"]

    def test_cors_origins_empty_values(self):
        """Test CORS origins ignores empty values."""
        with patch.dict(os.environ, {"CORS_ORIGINS": "http://a.com,,http://b.com"}, clear=True):
            settings = Settings()
            assert settings.CORS_ORIGINS == ["http://a.com", "http://b.com"]

    def test_is_production_property(self):
        """Test is_production property."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True):
            settings = Settings()
            assert settings.is_production is True

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            settings = Settings()
            assert settings.is_production is False

    def test_database_url_or_sqlite_fallback(self):
        """Test database URL fallback to SQLite in development."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development", "DATABASE_URL": ""}, clear=True):
            settings = Settings()
            assert settings.database_url_or_sqlite == "sqlite:///./churn_dev.db"

    def test_database_url_or_sqlite_uses_postgres(self):
        """Test database URL uses PostgreSQL when provided."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost/db"}, clear=True):
            settings = Settings()
            assert settings.database_url_or_sqlite == "postgresql+psycopg2://user:pass@localhost/db"

    def test_database_url_required_in_production(self):
        """Test DATABASE_URL required in production."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "DATABASE_URL": ""}, clear=True):
            settings = Settings()
            with pytest.raises(RuntimeError, match="DATABASE_URL must be set in production"):
                _ = settings.database_url_or_sqlite

    def test_validate_production_config_missing_db(self):
        """Test production config validation fails without DATABASE_URL."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "DATABASE_URL": "", "MODEL_ARTIFACTS_BUCKET": "test-bucket", "MODEL_ARTIFACTS_KEY": "model_v1.joblib", "API_KEY": "a" * 32}, clear=True):
            settings = Settings()
            with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
                settings.validate_production_config()

    def test_validate_production_config_insecure_defaults(self):
        """Test production config validation fails with insecure defaults."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "DATABASE_URL": "postgresql+psycopg2://postgres:postgres@localhost/db", "MODEL_ARTIFACTS_BUCKET": "test-bucket", "MODEL_ARTIFACTS_KEY": "model_v1.joblib", "API_KEY": "a" * 32}, clear=True):
            settings = Settings()
            with pytest.raises(RuntimeError, match="insecure default credential"):
                settings.validate_production_config()

    def test_validate_production_config_pool_size_warning(self):
        """Test production config validation warns about excessive pool size."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "DATABASE_URL": "postgresql+psycopg2://user:pass@localhost/db", "DB_POOL_SIZE": "30", "DB_MAX_OVERFLOW": "30", "MODEL_ARTIFACTS_BUCKET": "test-bucket", "MODEL_ARTIFACTS_KEY": "model_v1.joblib", "API_KEY": "a" * 32}, clear=True):
            settings = Settings()
            with pytest.raises(RuntimeError, match="exceeds recommended maximum"):
                settings.validate_production_config()

    def test_validate_production_config_ok(self):
        """Test production config validation passes with valid config."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql+psycopg2://user:pass@localhost/db",
            "DB_POOL_SIZE": "5",
            "DB_MAX_OVERFLOW": "10",
            "MODEL_ARTIFACTS_BUCKET": "test-bucket",
            "MODEL_ARTIFACTS_KEY": "model_v1.joblib",
            "API_KEY": "a" * 32  # 32-char API key
        }, clear=True):
            settings = Settings()
            settings.validate_production_config()  # Should not raise

    def test_get_settings_caching(self):
        """Test get_settings returns cached instance."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            s1 = get_settings()
            s2 = get_settings()
            assert s1 is s2  # Should be same cached instance

    def test_validate_production_config_missing_model_artifact(self):
        """Test production config validation fails without MODEL_ARTIFACTS_BUCKET/KEY."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "DATABASE_URL": "postgresql+psycopg2://user:pass@localhost/db", "API_KEY": "a" * 32}, clear=True):
            settings = Settings()
            with pytest.raises(RuntimeError, match="MODEL_ARTIFACTS_BUCKET and MODEL_ARTIFACTS_KEY must be set"):
                settings.validate_production_config()

    def test_validate_production_config_missing_api_key(self):
        """Test production config validation fails without API_KEY."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "DATABASE_URL": "postgresql+psycopg2://user:pass@localhost/db", "MODEL_ARTIFACTS_BUCKET": "test-bucket", "MODEL_ARTIFACTS_KEY": "model_v1.joblib"}, clear=True):
            settings = Settings()
            with pytest.raises(RuntimeError, match="API_KEY is required in production"):
                settings.validate_production_config()

    def test_validate_production_config_short_api_key(self):
        """Test production config validation fails with short API_KEY."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "DATABASE_URL": "postgresql+psycopg2://user:pass@localhost/db", "MODEL_ARTIFACTS_BUCKET": "test-bucket", "MODEL_ARTIFACTS_KEY": "model_v1.joblib", "API_KEY": "short"}, clear=True):
            settings = Settings()
            with pytest.raises(RuntimeError, match="API_KEY must be at least 32 characters"):
                settings.validate_production_config()
