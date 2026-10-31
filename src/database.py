"""
Database engine and session management with lazy initialization.

This module provides lazy engine initialization so that importing application
modules does not require a working PostgreSQL service. The engine is created
on first use and can be overridden for testing.
"""

import logging
import threading
from typing import Any, Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.config import get_settings

# Thread-safe lazy initialization
_engine_lock = threading.RLock()
_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None

Base = declarative_base()

logger = logging.getLogger(__name__)


def _create_engine_from_settings() -> Engine:
    """Create SQLAlchemy engine from application settings."""
    settings = get_settings()
    database_url = settings.database_url_or_sqlite

    # Configure engine based on database type
    if database_url.startswith("sqlite"):
        # SQLite specific configuration with WAL mode and timeout for concurrency
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False, "timeout": 30},
            poolclass=None,  # Disable pooling for SQLite
        )

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")
            cursor.close()

        logger.info("Created SQLite engine (WAL mode enabled, pooling disabled)")
    else:
        # PostgreSQL configuration with connection pooling
        pool_size = settings.DB_POOL_SIZE
        max_overflow = settings.DB_MAX_OVERFLOW
        pool_timeout = settings.DB_POOL_TIMEOUT
        pool_recycle = settings.DB_POOL_RECYCLE
        pool_pre_ping = settings.DB_POOL_PRE_PING

        engine = create_engine(
            database_url,
            pool_pre_ping=pool_pre_ping,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
        )
        logger.info(
            "Created PostgreSQL engine: pool_size=%d, max_overflow=%d, "
            "pool_timeout=%d, pool_recycle=%d, pool_pre_ping=%s",
            pool_size, max_overflow, pool_timeout, pool_recycle, pool_pre_ping
        )

        # Log pool statistics periodically in production
        if settings.is_production:
            @event.listens_for(engine, "checkout")
            def _on_checkout(
                dbapi_connection: Any, connection_record: Any, connection_proxy: Any
            ) -> None:
                """Log pool status on checkout for monitoring."""
                pool = engine.pool
                size = pool.size() if callable(getattr(pool, "size", None)) else getattr(pool, "size", 0)  # type: ignore[attr-defined]
                checked_out = (
                    pool.checkedout() if callable(getattr(pool, "checkedout", None)) else getattr(pool, "checkedout", 0)  # type: ignore[attr-defined]
                )
                overflow = (
                    pool.overflow() if callable(getattr(pool, "overflow", None)) else getattr(pool, "overflow", 0)  # type: ignore[attr-defined]
                )
                logger.debug(
                    "Pool status: size=%d, checked_out=%d, overflow=%d",
                    size, checked_out, overflow
                )

    return engine


def get_engine() -> Engine:
    """
    Get the database engine, creating it lazily on first access.

    Returns:
        SQLAlchemy Engine instance.
    """
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = _create_engine_from_settings()
    return _engine


def get_session_factory() -> sessionmaker:
    """
    Get the session factory, creating it lazily on first access.

    Returns:
        SQLAlchemy sessionmaker instance.
    """
    global _session_factory
    if _session_factory is None:
        with _engine_lock:
            if _session_factory is None:
                _session_factory = sessionmaker(
                    autocommit=False,
                    autoflush=False,
                    bind=get_engine(),
                )
    return _session_factory


def set_engine(engine: Engine) -> None:
    """
    Set a custom engine (primarily for testing).

    This replaces the current engine and session factory. Use with caution
    as it affects all subsequent database operations.

    Args:
        engine: SQLAlchemy Engine instance to use.
    """
    global _engine, _session_factory
    with _engine_lock:
        _engine = engine
        _session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )


def dispose_engine() -> None:
    """
    Dispose of the current engine and reset to None.

    This should be called during application shutdown or test teardown
    to properly dispose of connection pools.
    """
    global _engine, _session_factory
    with _engine_lock:
        if _engine is not None:
            logger.info("Disposing database engine and connection pool")
            _engine.dispose()
            _engine = None
            _session_factory = None


def get_db() -> Generator[Session, None, None]:
    """
    Dependency generator for FastAPI endpoints to get a DB session.

    Creates a new session for each request and ensures it's closed
    after the request completes, even if an exception occurs.

    Yields:
        SQLAlchemy Session instance.
    """
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_database() -> None:
    """
    Initialize the database by creating all tables.

    This should be called during application startup or test setup
    to ensure the database schema exists.
    """
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def drop_database() -> None:
    """
    Drop all database tables.

    This should be called during test teardown or application shutdown
    to clean up the database.
    """
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)


def get_pool_status() -> dict:
    """
    Get current connection pool status for monitoring.

    Returns:
        Dictionary with pool statistics.
    """
    engine = get_engine()
    pool = engine.pool
    # Handle different pool types (SQLite vs PostgreSQL)
    size = pool.size() if callable(getattr(pool, "size", None)) else getattr(pool, "size", 0)  # type: ignore[attr-defined]
    checked_out = (
        pool.checkedout() if callable(getattr(pool, "checkedout", None)) else getattr(pool, "checkedout", 0)  # type: ignore[attr-defined]
    )
    overflow = (
        pool.overflow() if callable(getattr(pool, "overflow", None)) else getattr(pool, "overflow", 0)  # type: ignore[attr-defined]
    )
    return {
        "size": size,
        "checked_out": checked_out,
        "overflow": overflow,
        "total": size + overflow,
    }
