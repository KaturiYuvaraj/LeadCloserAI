"""
Database Connection & SQLAlchemy Session Management.
Supports PostgreSQL (with connection pooling) when configured,
and canonical SQLite for seamless zero-delay local operation and testing.
"""

import os
from pathlib import Path
from typing import Generator

try:
    from loguru import logger  # type: ignore
except ImportError:
    import logging
    logger = logging.getLogger("core.db")  # type: ignore

from sqlalchemy import create_engine  # type: ignore
from sqlalchemy.orm import sessionmaker, Session, declarative_base  # type: ignore

Base = declarative_base()

# Canonical absolute path for SQLite database so all processes share the exact same database
CANONICAL_SQLITE_PATH = (Path(__file__).resolve().parent.parent / "leads_crm.db").resolve()
CANONICAL_SQLITE_URL = f"sqlite:///{CANONICAL_SQLITE_PATH.as_posix()}"

# If DATABASE_URL is not set, default directly to canonical SQLite for local development
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL or not DATABASE_URL.strip():
    DATABASE_URL = CANONICAL_SQLITE_URL

# Engine configuration
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
            f"Could not connect to configured PostgreSQL ({exc}). "
            f"Falling back to canonical SQLite database ({CANONICAL_SQLITE_PATH.name})."
        )
        DATABASE_URL = CANONICAL_SQLITE_URL
        engine = create_engine(CANONICAL_SQLITE_URL, connect_args={"check_same_thread": False}, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
