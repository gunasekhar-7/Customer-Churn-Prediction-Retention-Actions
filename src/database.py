"""
Database engine and session management with lazy initialization.

This module provides lazy engine initialization so that importing application
modules does not require a working PostgreSQL service. The engine is created
on first use and can be overridden for testing.
"""

import threading
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.config import get_settings

# Thread-safe lazy initialization
_engine_lock = threading.Lock()
_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None

Base = declarative_base()


def _create_engine_from_settings() -> Engine:
    """Create SQLAlchemy engine from application settings."""
    settings = get_settings()
    database_url = settings.database_url_or_sqlite

    # Configure engine based on database type
    if database_url.startswith("sqlite"):
        # SQLite specific configuration
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=None,  # Disable pooling for SQLite
        )
    else:
        # PostgreSQL configuration with connection pooling
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
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
