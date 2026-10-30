"""
Centralized application configuration using Pydantic Settings.

All configuration is loaded from environment variables with safe defaults for local development.
Production deployments MUST provide all required secrets via environment variables.
"""

from functools import lru_cache
from typing import List

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Attributes:
        # API Configuration
        API_HOST: Host to bind the API server to.
        API_PORT: Port to bind the API server to.
        API_WORKERS: Number of worker processes for production.

        # Database Configuration
        DATABASE_URL: PostgreSQL connection URL. Must be provided in production.
                      Uses psycopg2 driver explicitly.

        # Database Connection Pool Configuration
        DB_POOL_SIZE: Base connection pool size per worker process.
        DB_MAX_OVERFLOW: Maximum overflow connections per worker.
        DB_POOL_TIMEOUT: Seconds to wait for a connection from the pool.
        DB_POOL_RECYCLE: Seconds after which a connection is recycled.
        DB_POOL_PRE_PING: Enable connection health checks before use.

        # Rate Limiting Configuration
        RATE_LIMIT_ENABLED: Enable/disable rate limiting globally.
        RATE_LIMIT_DEFAULT: Default rate limit (requests per minute).
        RATE_LIMIT_PREDICT: Rate limit for /predict endpoint (requests per minute).
        RATE_LIMIT_BATCH: Rate limit for /predict/batch endpoint (requests per minute).
        RATE_LIMIT_BATCH_MAX_SIZE: Maximum number of customers in a batch request.

        # CORS Configuration
        CORS_ORIGINS: Comma-separated list of allowed CORS origins.
                      Use "*" for development only.

        # Logging Configuration
        LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR).
        LOG_FORMAT: Log format (json, text).

        # Environment
        ENVIRONMENT: Deployment environment (development, staging, production).

        # Data Retention Configuration
        DATA_RETENTION_DAYS: Retention period for prediction records in days.
                              Records older than this will be deleted by cleanup job.
        DATA_RETENTION_BATCH_SIZE: Batch size for retention cleanup job to avoid long transactions.
        DATA_RETENTION_DRY_RUN: If true, cleanup job only logs what would be deleted without deleting.

        # Data Minimization Configuration
        DATA_MINIMIZATION_ENABLED: Enable data minimization - store only necessary fields in raw_features.

        # Uvicorn Runtime Configuration
        UVICORN_KEEP_ALIVE_TIMEOUT: Keep-alive timeout in seconds.
        UVICORN_WORKER_TIMEOUT: Worker timeout in seconds.
        UVICORN_LIMIT_CONCURRENCY: Maximum concurrent connections per worker.
        UVICORN_BACKLOG: Connection backlog size.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # API Configuration
    API_HOST: str = Field(default="0.0.0.0", description="API server host")
    API_PORT: int = Field(default=8000, description="API server port")
    API_WORKERS: int = Field(default=2, description="Number of worker processes (default 2 for 512CPU/1024MB)")

    # Database Configuration
    DATABASE_URL: str = Field(
        default="",
        description="PostgreSQL connection URL (required in production)",
    )

    # Database Connection Pool Configuration
    DB_POOL_SIZE: int = Field(default=5, description="Base connection pool size per worker")
    DB_MAX_OVERFLOW: int = Field(default=10, description="Maximum overflow connections per worker")
    DB_POOL_TIMEOUT: int = Field(default=30, description="Seconds to wait for a connection from the pool")
    DB_POOL_RECYCLE: int = Field(default=1800, description="Seconds after which a connection is recycled")
    DB_POOL_PRE_PING: bool = Field(default=True, description="Enable connection health checks before use")

    # Rate Limiting Configuration
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable rate limiting")
    RATE_LIMIT_DEFAULT: str = Field(
        default="100/minute", description="Default rate limit"
    )
    RATE_LIMIT_PREDICT: str = Field(
        default="60/minute", description="Rate limit for /predict endpoint"
    )
    RATE_LIMIT_BATCH: str = Field(
        default="10/minute", description="Rate limit for /predict/batch endpoint"
    )
    RATE_LIMIT_BATCH_MAX_SIZE: int = Field(
        default=100, description="Maximum batch size for /predict/batch"
    )

    # CORS Configuration
    CORS_ORIGINS: str = Field(
        default="http://localhost:8501,http://127.0.0.1:8501",
        description="Allowed CORS origins (comma-separated)",
    )

    # Logging Configuration
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(default="json", description="Log format (json, text)")

    # Environment
    ENVIRONMENT: str = Field(
        default="development", description="Deployment environment"
    )

    # Data Retention Configuration
    DATA_RETENTION_DAYS: int = Field(
        default=90,
        description="Retention period for prediction records in days. "
                    "Records older than this will be deleted by cleanup job."
    )
    DATA_RETENTION_BATCH_SIZE: int = Field(
        default=1000,
        description="Batch size for retention cleanup job to avoid long transactions"
    )
    DATA_RETENTION_DRY_RUN: bool = Field(
        default=False,
        description="If true, cleanup job only logs what would be deleted without deleting"
    )

    # Data Minimization Configuration
    DATA_MINIMIZATION_ENABLED: bool = Field(
        default=True,
        description="Enable data minimization - store only necessary fields in raw_features"
    )

    # Uvicorn Runtime Configuration
    UVICORN_KEEP_ALIVE_TIMEOUT: int = Field(default=75, description="Keep-alive timeout in seconds (should exceed ALB idle timeout)")
    UVICORN_WORKER_TIMEOUT: int = Field(default=120, description="Worker timeout in seconds")
    UVICORN_LIMIT_CONCURRENCY: int = Field(default=1000, description="Maximum concurrent connections per worker")
    UVICORN_BACKLOG: int = Field(default=2048, description="Connection backlog size")

    # Redis Configuration (for distributed rate limiting)
    REDIS_URL: str = Field(
        default="", description="Redis connection URL for distributed rate limiting (production)"
    )
    REDIS_TLS: bool = Field(
        default=False, description="Use TLS for Redis connection"
    )

    # Security Configuration
    API_KEY: str = Field(
        default="", description="API key for authentication (required in production)"
    )
    API_KEYS: str = Field(
        default="", description="Comma-separated list of API keys for rotation (production). If set, any matching key is accepted."
    )
    API_KEY_HEADER: str = Field(
        default="X-API-Key", description="HTTP header name for API key authentication"
    )

    # Model Artifact Configuration (for S3/remote storage)
    MODEL_ARTIFACTS_BUCKET: str = Field(
        default="", description="S3 bucket for model artifacts (production)"
    )
    MODEL_ARTIFACTS_KEY: str = Field(
        default="", description="S3 key for model artifact (production)"
    )
    MODEL_ARTIFACT_LOCAL_PATH: str = Field(
        default="models/model_v1.joblib", description="Local fallback path for model artifact"
    )

    # Drift Alert Webhook Configuration
    DRIFT_WEBHOOK_URL: str = Field(
        default="", description="Webhook URL for drift alerts (Slack, PagerDuty, HTTP). Empty disables."
    )
    DRIFT_WEBHOOK_SECRET: str = Field(
        default="", description="Optional secret for webhook signature verification (HMAC-SHA256)"
    )
    DRIFT_WEBHOOK_TIMEOUT: int = Field(
        default=5, description="Webhook request timeout in seconds"
    )

    # Drift Detection Configuration
    DRIFT_PSI_THRESHOLD: float = Field(
        default=0.1, description="PSI threshold for drift alert"
    )
    DRIFT_PSI_WARNING: float = Field(
        default=0.05, description="PSI threshold for drift warning"
    )
    DRIFT_KS_THRESHOLD: float = Field(
        default=0.05, description="KS test p-value threshold for drift"
    )
    DRIFT_MIN_SAMPLES: int = Field(
        default=100, description="Minimum samples for drift detection"
    )
    DRIFT_WINDOW_SIZE: int = Field(
        default=1000, description="Rolling window size for drift detection"
    )
    DRIFT_EVALUATION_INTERVAL_SEC: int = Field(
        default=300, description="Drift evaluation interval in seconds"
    )
    DRIFT_FEATURE_PSI_THRESHOLD: float = Field(
        default=0.1, description="Feature-level PSI threshold"
    )
    DRIFT_FEATURE_KS_THRESHOLD: float = Field(
        default=0.05, description="Feature-level KS threshold"
    )

    # Pseudonymization Configuration
    PSEUDONYMIZATION_SALT: str = Field(
        default="", description="Salt for customer ID pseudonymization (SHA-256). Required in production."
    )
    PSEUDONYMIZATION_ENABLED: bool = Field(
        default=True, description="Enable customer ID pseudonymization in database"
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL is provided and uses correct driver."""
        if not v:
            return v  # Allow empty for local development with SQLite fallback
        if v.startswith("postgresql://") and not v.startswith(
            "postgresql+psycopg2://"
        ):
            return v.replace("postgresql://", "postgresql+psycopg2://", 1)
        return v

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        allowed = ["development", "staging", "production"]
        if v.lower() not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}")
        return v.lower()

    @field_validator("DRIFT_WEBHOOK_SECRET")
    @classmethod
    def validate_webhook_secret(cls, v: str, info: ValidationInfo) -> str:
        """Require webhook secret if webhook URL is configured."""
        # Note: We can't easily access other fields in field_validator without model_validator
        # This will be validated in validate_production_config
        return v

    @field_validator("CORS_ORIGINS")
    @classmethod
    def parse_cors_origins(cls, v: str) -> List[str]:
        """Parse comma-separated CORS origins."""
        return [origin.strip() for origin in v.split(",") if origin.strip()]

    @field_validator("DRIFT_WEBHOOK_URL")
    @classmethod
    def validate_webhook_url(cls, v: str) -> str:
        """Validate webhook URL format if provided."""
        if v and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("DRIFT_WEBHOOK_URL must be a valid HTTP/HTTPS URL")
        return v

    @model_validator(mode="after")
    def validate_webhook_config(self) -> "Settings":
        """Require webhook secret if webhook URL is set."""
        if self.DRIFT_WEBHOOK_URL and not self.DRIFT_WEBHOOK_SECRET:
            raise ValueError(
                "DRIFT_WEBHOOK_SECRET is required when DRIFT_WEBHOOK_URL is configured"
            )
        return self

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == "production"

    @property
    def database_url_or_sqlite(self) -> str:
        """
        Return DATABASE_URL if set, otherwise fall back to SQLite for local development.
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        # Local development fallback - SQLite in-memory for tests, file-based for dev
        if self.is_production:
            raise RuntimeError(
                "DATABASE_URL must be set in production environment"
            )
        return "sqlite:///./churn_dev.db"

    @property
    def api_keys(self) -> List[str]:
        """
        Get all valid API keys as a list.

        Supports both single API_KEY and comma-separated API_KEYS for rotation.
        Returns empty list if neither is configured.
        """
        keys = []
        if self.API_KEY:
            keys.append(self.API_KEY)
        if self.API_KEYS:
            keys.extend([k.strip() for k in self.API_KEYS.split(",") if k.strip()])
        return keys

    def validate_production_config(self) -> None:
        """
        Validate all required production settings are configured.
        Raises RuntimeError if any required setting is missing or insecure.
        """
        if not self.is_production:
            return

        errors: list[str] = []
        self._validate_database_config(errors)
        self._validate_pool_config(errors)
        self._validate_model_artifact_config(errors)
        self._validate_api_key_config(errors)
        self._validate_pseudonymization_config(errors)

        if errors:
            raise RuntimeError(
                "Production configuration validation failed:\n" + "\n".join(errors)
            )

    def _validate_database_config(self, errors: list) -> None:
        """Validate database configuration."""
        if not self.DATABASE_URL:
            errors.append("DATABASE_URL is required in production")

        insecure_defaults = [
            "postgres:postgres",
            "postgres:postgrespassword",
        ]
        for insecure in insecure_defaults:
            if insecure in self.DATABASE_URL:
                errors.append(
                    f"DATABASE_URL contains insecure default credential: {insecure}"
                )

    def _validate_pool_config(self, errors: list) -> None:
        """Validate connection pool settings."""
        max_connections_per_worker = self.DB_POOL_SIZE + self.DB_MAX_OVERFLOW
        if max_connections_per_worker > 50:
            errors.append(
                f"DB_POOL_SIZE + DB_MAX_OVERFLOW ({max_connections_per_worker}) exceeds recommended maximum of 50 per worker"
            )

    def _validate_model_artifact_config(self, errors: list) -> None:
        """Validate model artifact configuration."""
        if not self.MODEL_ARTIFACTS_BUCKET and not self.MODEL_ARTIFACTS_KEY:
            errors.append(
                "MODEL_ARTIFACTS_BUCKET and MODEL_ARTIFACTS_KEY must be set in production for model artifact loading"
            )

    def _validate_api_key_config(self, errors: list) -> None:
        """Validate API key configuration."""
        if not self.API_KEY:
            errors.append("API_KEY is required in production")
        elif len(self.API_KEY) < 32:
            errors.append("API_KEY must be at least 32 characters for security")

    def _validate_pseudonymization_config(self, errors: list) -> None:
        """Validate pseudonymization configuration."""
        if self.PSEUDONYMIZATION_ENABLED and not self.PSEUDONYMIZATION_SALT:
            errors.append("PSEUDONYMIZATION_SALT is required when PSEUDONYMIZATION_ENABLED is true in production")
        elif self.PSEUDONYMIZATION_ENABLED and len(self.PSEUDONYMIZATION_SALT) < 16:
            errors.append("PSEUDONYMIZATION_SALT must be at least 16 characters for security")


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Returns:
        Settings: Application configuration instance.
    """
    return Settings()


# Convenience function for backward compatibility
def get_database_url() -> str:
    """Get database URL with SQLite fallback for development."""
    return get_settings().database_url_or_sqlite
