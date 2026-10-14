import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Fallback to local postgres if not provided by Docker
# Use psycopg2 driver explicitly since psycopg2-binary is in dependencies
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/churn_db")

# For testing, we might pass an sqlite in-memory url
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """
    Dependency generator for FastAPI endpoints to get a DB session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
