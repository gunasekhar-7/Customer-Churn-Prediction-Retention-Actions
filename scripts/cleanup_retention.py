#!/usr/bin/env python
"""
Data Retention Cleanup Script.

This script deletes or anonymizes prediction records older than the configured
retention period. It can be run as a scheduled job (cron, Kubernetes CronJob, etc.)

Usage:
    python scripts/cleanup_retention.py [--dry-run] [--retention-days DAYS] [--batch-size SIZE]

Environment Variables:
    DATABASE_URL: PostgreSQL connection URL (required in production)
    DATA_RETENTION_DAYS: Retention period in days (default: 90)
    DATA_RETENTION_BATCH_SIZE: Batch size for cleanup (default: 1000)
    DATA_RETENTION_DRY_RUN: If "true", only log what would be deleted (default: false)
    ENVIRONMENT: Deployment environment (development, staging, production)
"""

import argparse
import logging
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config import Settings
from src.data_protection import cleanup_expired_records, get_retention_stats
from src.database import Base, create_engine, sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Data retention cleanup job')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Only log what would be deleted without actually deleting'
    )
    parser.add_argument(
        '--retention-days',
        type=int,
        help='Override retention period in days'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        help='Override batch size for cleanup'
    )
    parser.add_argument(
        '--stats-only',
        action='store_true',
        help='Only show retention statistics without running cleanup'
    )
    return parser.parse_args()


def _configure_settings(args: argparse.Namespace) -> Settings:
    """Load and configure settings from args."""
    settings = Settings()

    if args.dry_run:
        settings.DATA_RETENTION_DRY_RUN = True
    if args.retention_days:
        settings.DATA_RETENTION_DAYS = args.retention_days
    if args.batch_size:
        settings.DATA_RETENTION_BATCH_SIZE = args.batch_size

    return settings


def _get_database_url(settings: Settings) -> str:
    """Get database URL with fallback for development."""
    if not settings.DATABASE_URL:
        if settings.is_production:
            logger.error("DATABASE_URL is required in production environment")
            sys.exit(1)
        logger.warning("DATABASE_URL not set, using SQLite fallback for development")
        return "sqlite:///./churn_dev.db"
    return settings.DATABASE_URL


def _create_db_session(database_url: str):
    """Create database engine and session factory."""
    logger.info(f"Connecting to database: {database_url.split('@')[-1] if '@' in database_url else database_url}")
    connect_args = {"check_same_thread": False} if 'sqlite' in database_url else {}
    engine = create_engine(database_url, connect_args=connect_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return engine, SessionLocal


def _run_stats_only(db, retention_days: int) -> None:
    """Run statistics only mode."""
    stats = get_retention_stats(db, retention_days)
    logger.info("Retention Statistics:")
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")


def _run_cleanup(db, settings: Settings) -> dict:
    """Run the cleanup job and return results."""
    result = cleanup_expired_records(
        db=db,
        retention_days=settings.DATA_RETENTION_DAYS,
        batch_size=settings.DATA_RETENTION_BATCH_SIZE,
        dry_run=settings.DATA_RETENTION_DRY_RUN,
    )
    return result


def _handle_cleanup_result(result: dict, dry_run: bool) -> None:
    """Log cleanup results and handle exit codes."""
    logger.info("Cleanup completed successfully")
    for key, value in result.items():
        logger.info(f"  {key}: {value}")

    if dry_run and result['deleted_prediction_records'] > 0:
        logger.warning(
            f"DRY RUN: {result['deleted_prediction_records']} records would be deleted. "
            "Run without --dry-run to perform actual deletion."
        )
        sys.exit(1)


def main() -> None:
    """Main entry point for the cleanup script."""
    args = _parse_args()
    settings = _configure_settings(args)
    database_url = _get_database_url(settings)
    engine, SessionLocal = _create_db_session(database_url)

    db = SessionLocal()
    try:
        if args.stats_only:
            _run_stats_only(db, settings.DATA_RETENTION_DAYS)
            return

        result = _run_cleanup(db, settings)
        _handle_cleanup_result(result, settings.DATA_RETENTION_DRY_RUN)

    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
