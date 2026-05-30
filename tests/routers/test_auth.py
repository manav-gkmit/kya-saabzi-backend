"""Integration tests for /api/v1/auth endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.households import Household

pytestmark = pytest.mark.asyncio

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


async def _register(async_client: AsyncClient, **overrides):
    payload = {**_REG_PAYLOAD, **overrides}
    return await async_client.post(REG_URL, json=payload)


async def _login(async_client: AsyncClient, email: str, password: str):
    return await async_client.post(LOGIN_URL, json={"email": email, "password": password})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegister:
    """POST /api/v1/auth/register"""

    async def test_creates_user_and_household(self, async_client: AsyncClient) -> None:
        resp = await _register(async_client)
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "newuser@example.com"
        assert body["username"] == "newuser"
        assert body["household_id"] is not None

    async def test_register_with_invite_code(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        resp = await _register(
            async_client,
            email="invite@example.com",
            username="inviteuser",
            invite_code=async_test_household.invite_code,
        )
        assert resp.status_code == 201
        assert resp.json()["household_id"] == str(async_test_household.id)

    async def test_invalid_invite_code(self, async_client: AsyncClient) -> None:
        resp = await _register(async_client, invite_code="ZZZZZZZZ")
        assert resp.status_code == 404

    async def test_duplicate_email(self, async_client: AsyncClient) -> None:
        await _register(async_client)
        resp = await _register(async_client, username="different")
        assert resp.status_code == 409

    async def test_duplicate_username(self, async_client: AsyncClient) -> None:
        await _register(async_client)
        resp = await _register(async_client, email="other@example.com")
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


class TestLogin:
    """POST /api/v1/auth/login"""

    async def test_success(self, async_client: AsyncClient) -> None:
        await _register(async_client)
        resp = await _login(async_client, "newuser@example.com", "StrongP@ss1")
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["user"]["email"] == "newuser@example.com"

    async def test_wrong_email(self, async_client: AsyncClient) -> None:
        await _register(async_client)
        resp = await _login(async_client, "wrong@example.com", "StrongP@ss1")
        assert resp.status_code == 401

    async def test_wrong_password(self, async_client: AsyncClient) -> None:
        await _register(async_client)
        resp = await _login(async_client, "newuser@example.com", "wrongpass")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    """POST /api/v1/auth/refresh"""

    async def test_rotation_returns_new_pair(self, async_client: AsyncClient) -> None:
        await _register(async_client)
        login_resp = await _login(async_client, "newuser@example.com", "StrongP@ss1")
        old_refresh = login_resp.json()["refresh_token"]

        resp = await async_client.post(REFRESH_URL, json={"refresh_token": old_refresh})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["refresh_token"] != old_refresh

    async def test_reused_token_returns_401(self, async_client: AsyncClient) -> None:
        await _register(async_client)
        login_resp = await _login(async_client, "newuser@example.com", "StrongP@ss1")
        old_refresh = login_resp.json()["refresh_token"]

        # First use — valid rotation
        first_resp = await async_client.post(REFRESH_URL, json={"refresh_token": old_refresh})
        assert first_resp.status_code == 200

        # Second use — reuse detected
        resp = await async_client.post(REFRESH_URL, json={"refresh_token": old_refresh})
        assert resp.status_code == 401

    async def test_invalid_token_returns_401(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(REFRESH_URL, json={"refresh_token": "fake-token"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


class TestLogout:
    """POST /api/v1/auth/logout and /logout/all"""

    async def test_single_device_logout(self, async_client: AsyncClient) -> None:
        await _register(async_client)
        login_resp = await _login(async_client, "newuser@example.com", "StrongP@ss1")
        refresh = login_resp.json()["refresh_token"]

        resp = await async_client.post(LOGOUT_URL, json={"refresh_token": refresh})
        assert resp.status_code == 204

    async def test_logout_all_sessions(
        self,
        async_client: AsyncClient,
        async_auth_headers: dict,
    ) -> None:
        resp = await async_client.post(LOGOUT_ALL_URL, headers=async_auth_headers)
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


class TestProfile:
    """GET /api/v1/auth/me"""

    async def test_authenticated(self, async_client: AsyncClient, async_auth_headers: dict) -> None:
        resp = await async_client.get(ME_URL, headers=async_auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"

    async def test_unauthenticated(self, async_client: AsyncClient) -> None:
        resp = await async_client.get(ME_URL)
        assert resp.status_code in (401, 403)
