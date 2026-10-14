"""
Centralized application configuration using Pydantic Settings.

All configuration is loaded from environment variables with safe defaults for local development.
Production deployments MUST provide all required secrets via environment variables.
"""

from functools import lru_cache
from typing import Any, List

from pydantic import Field, field_validator
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

        # Security Configuration
        API_KEY: Secret API key for authentication. Required in production.
                 Must be a strong random string (min 32 chars recommended).
        API_KEY_HEADER: HTTP header name for API key authentication.

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

        # Environment
        ENVIRONMENT: Deployment environment (development, staging, production).
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
    API_WORKERS: int = Field(default=1, description="Number of worker processes")

    # Database Configuration
    DATABASE_URL: str = Field(
        default="",
        description="PostgreSQL connection URL (required in production)",
    )

    # Security Configuration
    API_KEY: str = Field(
        default="",
        description="API key for authentication (required in production)",
    )
    API_KEY_HEADER: str = Field(
        default="X-API-Key", description="HTTP header for API key"
    )

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

    @field_validator("API_KEY")
    @classmethod
    def validate_api_key(cls, v: str, info: Any) -> str:
        """Validate API key is set in production."""
        # Note: We can't easily access other fields here, so we'll check in the property
        return v

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        allowed = ["development", "staging", "production"]
        if v.lower() not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}")
        return v.lower()

    @field_validator("CORS_ORIGINS")
    @classmethod
    def parse_cors_origins(cls, v: str) -> List[str]:
        """Parse comma-separated CORS origins."""
        return [origin.strip() for origin in v.split(",") if origin.strip()]

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
    def api_key_or_dev_default(self) -> str:
        """
        Return API_KEY if set, otherwise generate a dev-only default.
        WARNING: Never use the dev default in production!
        """
        if self.API_KEY:
            return self.API_KEY
        if self.is_production:
            raise RuntimeError(
                "API_KEY must be set in production environment. "
                "Generate a secure random key (min 32 chars)."
            )
        # Development-only default - clearly marked as insecure
        return "dev-insecure-key-change-in-production"

    def validate_production_config(self) -> None:
        """
        Validate all required production settings are configured.
        Raises RuntimeError if any required setting is missing or insecure.
        """
        if not self.is_production:
            return

        errors = []

        if not self.DATABASE_URL:
            errors.append("DATABASE_URL is required in production")

        if not self.API_KEY or self.API_KEY == "dev-insecure-key-change-in-production":
            errors.append(
                "API_KEY must be set to a secure random value in production "
                "(minimum 32 characters recommended)"
            )

        if len(self.API_KEY) < 32:
            errors.append(
                "API_KEY should be at least 32 characters for production security"
            )

        # Check for known insecure defaults
        insecure_defaults = [
            "postgres:postgres",
            "postgres:postgrespassword",
            "dev-insecure-key",
        ]
        for insecure in insecure_defaults:
            if insecure in self.DATABASE_URL:
                errors.append(
                    f"DATABASE_URL contains insecure default credential: {insecure}"
                )
            if insecure in self.API_KEY:
                errors.append(
                    f"API_KEY contains insecure default: {insecure}"
                )

        if errors:
            raise RuntimeError(
                "Production configuration validation failed:\n" + "\n".join(errors)
            )


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


def get_api_key() -> str:
    """Get API key with dev default warning."""
    return get_settings().api_key_or_dev_default
