"""
Pytest configuration and database fixtures for LeadCloser.AI.
Ensures tests run in isolated transactions with automatic rollback.
"""

import os
import sys
from pathlib import Path
import pytest
import pytest_asyncio
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.db import DATABASE_URL, Base
from main import app

engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Ensure all database tables exist and baseline seeded employees are populated."""
    Base.metadata.create_all(bind=engine)
    try:
        from database import init_db
        init_db()
    except Exception as e:
        print(f"Warning: init_db failed during test setup: {e}")
    yield


@pytest.fixture
def db_session():
    """
    Provides a transactional database session that rolls back all changes
    after each test, ensuring tests never leak state or depend on each other.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest_asyncio.fixture
async def async_client():
    """Provides an isolated AsyncClient for FastAPI endpoint testing."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
