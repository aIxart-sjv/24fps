"""
Pytest fixtures and configuration.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.storage.db import Base


@pytest.fixture(scope="function")
def test_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def test_db(test_engine):
    """Provide a test database session."""
    SessionLocal = sessionmaker(bind=test_engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def test_client(test_engine):
    """Provide a FastAPI test client."""
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.storage.db import get_db

    SessionLocal = sessionmaker(bind=test_engine, expire_on_commit=False)

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.rollback()
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)
