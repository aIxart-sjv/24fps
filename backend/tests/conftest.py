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


@pytest.fixture
def make_authenticated_headers(test_db, test_client):
    """Factory fixture: create a user with the given role and return the
    `Authorization` header for them (Phase 25, "Case-Level Access
    Control").

    Defaults to `UserRole.ADMIN` -- most tests using this predate Phase 25
    and exercise a specific business-logic endpoint that happens to now
    require *some* authenticated caller with case access; an admin's
    unconditional access keeps those tests focused on what they actually
    test, rather than incidentally becoming access-control tests too. Pass
    `role=UserRole.OFFICER` (and separately grant case access, e.g. via
    `app.core.case_authorization_service.CaseAuthorizationService.
    grant_case_access`) when a test specifically means to exercise
    officer-scoped access.
    """
    from app.core.auth_manager import AuthManager
    from app.models import UserRole

    counter = {"n": 0}

    def _make(
        role: UserRole = UserRole.ADMIN,
        username: str | None = None,
        password: str = "password123",
    ) -> dict[str, str]:
        counter["n"] += 1
        uname = username or f"phase25_testuser_{counter['n']}"
        AuthManager.create_user(
            test_db, username=uname, display_name=uname.title(), password=password, role=role
        )
        resp = test_client.post(
            "/api/v1/auth/login", json={"username": uname, "password": password}
        )
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['token']}"}

    return _make
