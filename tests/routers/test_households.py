"""Integration tests for /api/v1/households endpoints (entirely new)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.households import Household
from app.models.users import User
from app.utils.tokens import create_access_token

pytestmark = pytest.mark.asyncio

ME_URL = "/api/v1/households/me"
MEMBERS_URL = "/api/v1/households/me/members"
JOIN_URL = "/api/v1/households/join"
LEAVE_URL = "/api/v1/households/leave"


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------


class TestGetMyHousehold:
    async def test_returns_household(
        self,
        async_client: AsyncClient,
        async_auth_headers: dict,
        async_test_household: Household,
    ) -> None:
        resp = await async_client.get(ME_URL, headers=async_auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(async_test_household.id)
        assert "invite_code" in body

    async def test_unauthenticated(self, async_client: AsyncClient) -> None:
        resp = await async_client.get(ME_URL)
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# PATCH /me
# ---------------------------------------------------------------------------


class TestUpdateMyHousehold:
    async def test_admin_updates_name(
        self,
        async_client: AsyncClient,
        async_auth_headers: dict,
    ) -> None:
        resp = await async_client.patch(
            ME_URL,
            json={"name": "New Name"},
            headers=async_auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    async def test_admin_updates_preferences(
        self,
        async_client: AsyncClient,
        async_auth_headers: dict,
    ) -> None:
        resp = await async_client.patch(
            ME_URL,
            json={"preferences": {"is_vegetarian": True}},
            headers=async_auth_headers,
        )
        assert resp.status_code == 200

    async def test_non_admin_returns_403(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_user: User,
        async_test_household: Household,
    ) -> None:
        other_user = User(
            email="other3@example.com",
            username="otheruser3",
            hashed_password="password",
            household_id=async_test_household.id,
        )
        async_db_session.add(other_user)
        await async_db_session.commit()
        await async_db_session.refresh(other_user)

        # test_user fixture sets admin_id on test_household
        token = create_access_token(subject=str(other_user.id))
        headers = {"Authorization": f"Bearer {token}"}
        resp = await async_client.patch(
            ME_URL,
            json={"name": "Nope"},
            headers=headers,
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /me/members
# ---------------------------------------------------------------------------


class TestGetMembers:
    async def test_returns_members(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_user: User,
        async_test_household: Household,
        async_auth_headers: dict,
    ) -> None:
        other_user = User(
            email="other4@example.com",
            username="otheruser4",
            hashed_password="password",
            household_id=async_test_household.id,
        )
        async_db_session.add(other_user)
        await async_db_session.commit()

        resp = await async_client.get(MEMBERS_URL, headers=async_auth_headers)
        assert resp.status_code == 200
        members = resp.json()
        ids = {m["id"] for m in members}
        assert str(async_test_user.id) in ids
        assert str(other_user.id) in ids


# ---------------------------------------------------------------------------
# POST /join
# ---------------------------------------------------------------------------


class TestJoinHousehold:
    async def test_valid_invite_code(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_user: User,
        async_auth_headers: dict,
    ) -> None:
        other_household = Household(name="Other Household")
        async_db_session.add(other_household)
        await async_db_session.commit()
        await async_db_session.refresh(other_household)

        resp = await async_client.post(
            JOIN_URL,
            json={"invite_code": other_household.invite_code},
            headers=async_auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == str(other_household.id)

    async def test_invalid_invite_code(
        self,
        async_client: AsyncClient,
        async_auth_headers: dict,
    ) -> None:
        resp = await async_client.post(
            JOIN_URL,
            json={"invite_code": "ZZZZZZZZ"},
            headers=async_auth_headers,
        )
        assert resp.status_code == 404

    async def test_already_member_is_noop(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_household: Household,
        async_auth_headers: dict,
    ) -> None:
        resp = await async_client.post(
            JOIN_URL,
            json={"invite_code": async_test_household.invite_code},
            headers=async_auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == str(async_test_household.id)


# ---------------------------------------------------------------------------
# POST /leave
# ---------------------------------------------------------------------------


class TestLeaveHousehold:
    async def test_sole_member_stays(
        self,
        async_client: AsyncClient,
        async_auth_headers: dict,
        async_test_household: Household,
    ) -> None:
        resp = await async_client.post(LEAVE_URL, headers=async_auth_headers)
        assert resp.status_code == 200
        # Should return the same household (no other members)
        assert resp.json()["id"] == str(async_test_household.id)

    async def test_leaves_creates_private(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_user: User,
        async_test_household: Household,
        async_auth_headers: dict,
    ) -> None:
        other_user = User(
            email="other5@example.com",
            username="otheruser5",
            hashed_password="password",
            household_id=async_test_household.id,
        )
        async_db_session.add(other_user)
        await async_db_session.commit()

        old_hh_id = str(async_test_household.id)
        user_id = str(async_test_user.id)
        resp = await async_client.post(LEAVE_URL, headers=async_auth_headers)
        assert resp.status_code == 200
        new_hh = resp.json()
        assert new_hh["id"] != old_hh_id
        assert new_hh["admin_id"] == user_id


# ---------------------------------------------------------------------------
# DELETE /me/members/{id}
# ---------------------------------------------------------------------------


class TestRemoveMember:
    async def test_admin_removes_member(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_user: User,
        async_test_household: Household,
        async_auth_headers: dict,
    ) -> None:
        other_user = User(
            email="other6@example.com",
            username="otheruser6",
            hashed_password="password",
            household_id=async_test_household.id,
        )
        async_db_session.add(other_user)
        await async_db_session.commit()
        await async_db_session.refresh(other_user)

        resp = await async_client.delete(
            f"{MEMBERS_URL}/{other_user.id}",
            headers=async_auth_headers,
        )
        assert resp.status_code == 204

    async def test_non_admin_returns_403(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        other_user = User(
            email="other7@example.com",
            username="otheruser7",
            hashed_password="password",
            household_id=async_test_household.id,
        )
        async_db_session.add(other_user)
        await async_db_session.commit()

        token = create_access_token(subject=str(other_user.id))
        headers = {"Authorization": f"Bearer {token}"}
        resp = await async_client.delete(
            f"{MEMBERS_URL}/{uuid.uuid4()}",
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_remove_self_returns_400(
        self,
        async_client: AsyncClient,
        async_test_user: User,
        async_auth_headers: dict,
    ) -> None:
        resp = await async_client.delete(
            f"{MEMBERS_URL}/{async_test_user.id}",
            headers=async_auth_headers,
        )
        assert resp.status_code == 422

    async def test_remove_nonexistent_returns_404(
        self,
        async_client: AsyncClient,
        async_auth_headers: dict,
    ) -> None:
        resp = await async_client.delete(
            f"{MEMBERS_URL}/{uuid.uuid4()}",
            headers=async_auth_headers,
        )
        assert resp.status_code == 404
