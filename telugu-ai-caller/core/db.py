"""
Database Connection & SQLAlchemy Session Management.
Supports PostgreSQL (with connection pooling) and fallback for local testing.
"""

import os
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from loguru import logger

Base = declarative_base()

# Canonical absolute path for SQLite fallback so all processes share the exact same database
CANONICAL_SQLITE_PATH = (Path(__file__).resolve().parent.parent / "leads_crm.db").resolve()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/leadcloser"
)

# Engine configuration with connection pooling for PostgreSQL
connect_args = {}
engine_kwargs = {"echo": False}

if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    engine_kwargs["connect_args"] = connect_args
    engine = create_engine(DATABASE_URL, **engine_kwargs)
else:
    connect_args["connect_timeout"] = 2
    engine_kwargs["connect_args"] = connect_args
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    engine_kwargs["pool_pre_ping"] = True
    try:
        test_engine = create_engine(DATABASE_URL, **engine_kwargs)
        with test_engine.connect() as conn:
            pass
        engine = test_engine
        logger.info(f"Connected to PostgreSQL database: {DATABASE_URL.split('@')[-1]}")
    except Exception as exc:
        logger.warning(
            f"Could not connect to PostgreSQL ({exc}). "
            "Falling back to local SQLite database so the app continues working."
        )
        sqlite_url = f"sqlite:///{CANONICAL_SQLITE_PATH.as_posix()}"
        DATABASE_URL = sqlite_url
        engine = create_engine(sqlite_url, connect_args={"check_same_thread": False}, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
