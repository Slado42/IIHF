"""
Test configuration and fixtures for the IIHF Fantasy Hockey backend.
Uses an in-memory SQLite database and a FastAPI TestClient.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.main import app

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db():
    """Yield a fresh in-memory SQLite session per test."""
    engine = create_engine(
        SQLALCHEMY_TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(scope="function")
def client(db):
    """TestClient with the test DB injected via dependency override."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_user(client):
    """Create a test user via POST /auth/signup."""
    payload = {
        "username": "testuser",
        "email": "test@test.com",
        "password": "password123",
    }
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 200, (
        f"Failed to create test_user: {response.status_code} {response.text}"
    )
    return response.json()


@pytest.fixture(scope="function")
def auth_headers(client, test_user):
    """Log in as test_user and return Authorization header dict with JWT."""
    # The /auth/login endpoint uses OAuth2PasswordRequestForm (form-encoded)
    response = client.post(
        "/auth/login",
        data={"username": "testuser", "password": "password123"},
    )
    assert response.status_code == 200, (
        f"Login failed: {response.status_code} {response.text}"
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
