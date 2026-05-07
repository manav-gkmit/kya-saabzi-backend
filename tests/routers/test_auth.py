"""Integration tests for /api/v1/auth endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.households import Household

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REG_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
LOGOUT_ALL_URL = "/api/v1/auth/logout/all"
ME_URL = "/api/v1/auth/me"

_REG_PAYLOAD = {
    "email": "newuser@example.com",
    "username": "newuser",
    "password": "StrongP@ss1",
}


def _register(client: TestClient, **overrides) -> dict:
    payload = {**_REG_PAYLOAD, **overrides}
    return client.post(REG_URL, json=payload)


def _login(client: TestClient, email: str, password: str) -> dict:
    return client.post(LOGIN_URL, json={"email": email, "password": password})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegister:
    """POST /api/v1/auth/register"""

    def test_creates_user_and_household(self, client: TestClient) -> None:
        resp = _register(client)
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "newuser@example.com"
        assert body["username"] == "newuser"
        assert body["household_id"] is not None

    def test_register_with_invite_code(
        self,
        client: TestClient,
        db_session: Session,
        test_household: Household,
    ) -> None:
        resp = _register(
            client,
            email="invite@example.com",
            username="inviteuser",
            invite_code=test_household.invite_code,
        )
        assert resp.status_code == 201
        assert resp.json()["household_id"] == str(test_household.id)

    def test_invalid_invite_code(self, client: TestClient) -> None:
        resp = _register(client, invite_code="ZZZZZZZZ")
        assert resp.status_code == 404

    def test_duplicate_email(self, client: TestClient) -> None:
        _register(client)
        resp = _register(client, username="different")
        assert resp.status_code == 409

    def test_duplicate_username(self, client: TestClient) -> None:
        _register(client)
        resp = _register(client, email="other@example.com")
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


class TestLogin:
    """POST /api/v1/auth/login"""

    def test_success(self, client: TestClient) -> None:
        _register(client)
        resp = _login(client, "newuser@example.com", "StrongP@ss1")
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["user"]["email"] == "newuser@example.com"

    def test_wrong_email(self, client: TestClient) -> None:
        _register(client)
        resp = _login(client, "wrong@example.com", "StrongP@ss1")
        assert resp.status_code == 401

    def test_wrong_password(self, client: TestClient) -> None:
        _register(client)
        resp = _login(client, "newuser@example.com", "wrongpass")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    """POST /api/v1/auth/refresh"""

    def test_rotation_returns_new_pair(self, client: TestClient) -> None:
        _register(client)
        login_resp = _login(client, "newuser@example.com", "StrongP@ss1")
        old_refresh = login_resp.json()["refresh_token"]

        resp = client.post(REFRESH_URL, json={"refresh_token": old_refresh})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["refresh_token"] != old_refresh

    def test_reused_token_returns_401(self, client: TestClient) -> None:
        _register(client)
        login_resp = _login(client, "newuser@example.com", "StrongP@ss1")
        old_refresh = login_resp.json()["refresh_token"]

        # First use — valid rotation
        client.post(REFRESH_URL, json={"refresh_token": old_refresh})

        # Second use — reuse detected
        resp = client.post(REFRESH_URL, json={"refresh_token": old_refresh})
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client: TestClient) -> None:
        resp = client.post(REFRESH_URL, json={"refresh_token": "fake-token"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


class TestLogout:
    """POST /api/v1/auth/logout and /logout/all"""

    def test_single_device_logout(self, client: TestClient) -> None:
        _register(client)
        login_resp = _login(client, "newuser@example.com", "StrongP@ss1")
        refresh = login_resp.json()["refresh_token"]

        resp = client.post(LOGOUT_URL, json={"refresh_token": refresh})
        assert resp.status_code == 204

    def test_logout_all_sessions(
        self,
        client: TestClient,
        auth_headers: dict,
    ) -> None:
        resp = client.post(LOGOUT_ALL_URL, headers=auth_headers)
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


class TestProfile:
    """GET /api/v1/auth/me"""

    def test_authenticated(self, client: TestClient, auth_headers: dict) -> None:
        resp = client.get(ME_URL, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"

    def test_unauthenticated(self, client: TestClient) -> None:
        resp = client.get(ME_URL)
        assert resp.status_code in (401, 403)
