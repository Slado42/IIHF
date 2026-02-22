"""
Tests for authentication endpoints: /auth/signup, /auth/login, /auth/me

Notes:
  - POST /auth/signup accepts JSON: {username, email, password}
  - POST /auth/login accepts OAuth2 form-encoded: username, password
  - GET /auth/me requires Bearer token
"""

import pytest


class TestSignup:
    def test_signup_success(self, client):
        """POST /auth/signup with valid data returns 200 and an access token."""
        payload = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "securepass1",
        }
        response = client.post("/auth/signup", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["access_token"]

    def test_signup_duplicate_username(self, client, test_user):
        """Signing up with an already-used username returns 400."""
        payload = {
            "username": "testuser",
            "email": "other@example.com",
            "password": "password123",
        }
        response = client.post("/auth/signup", json=payload)
        assert response.status_code == 400

    def test_signup_duplicate_email(self, client, test_user):
        """Signing up with an already-used e-mail returns 400."""
        payload = {
            "username": "differentuser",
            "email": "test@test.com",
            "password": "password123",
        }
        response = client.post("/auth/signup", json=payload)
        assert response.status_code == 400


class TestLogin:
    def test_login_success(self, client, test_user):
        """POST /auth/login with correct form credentials returns 200 and token."""
        response = client.post(
            "/auth/login",
            data={"username": "testuser", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["access_token"]

    def test_login_wrong_password(self, client, test_user):
        """POST /auth/login with wrong password returns 401."""
        response = client.post(
            "/auth/login",
            data={"username": "testuser", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    def test_login_wrong_username(self, client):
        """POST /auth/login with non-existent username returns 401."""
        response = client.post(
            "/auth/login",
            data={"username": "ghost", "password": "password123"},
        )
        assert response.status_code == 401


class TestGetMe:
    def test_get_me_authenticated(self, client, auth_headers):
        """GET /auth/me with a valid JWT returns 200 and user data."""
        response = client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@test.com"

    def test_get_me_unauthenticated(self, client):
        """GET /auth/me without any JWT returns 401."""
        response = client.get("/auth/me")
        assert response.status_code == 401
