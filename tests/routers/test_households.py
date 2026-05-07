"""Integration tests for /api/v1/households endpoints (entirely new)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.households import Household
from app.models.users import User
from app.utils.jwt import create_access_token

ME_URL = "/api/v1/households/me"
MEMBERS_URL = "/api/v1/households/me/members"
JOIN_URL = "/api/v1/households/join"
LEAVE_URL = "/api/v1/households/leave"


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------


class TestGetMyHousehold:
    def test_returns_household(
        self,
        client: TestClient,
        auth_headers: dict,
        test_household: Household,
    ) -> None:
        resp = client.get(ME_URL, headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(test_household.id)
        assert "invite_code" in body

    def test_unauthenticated(self, client: TestClient) -> None:
        resp = client.get(ME_URL)
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# PATCH /me
# ---------------------------------------------------------------------------


class TestUpdateMyHousehold:
    def test_admin_updates_name(
        self,
        client: TestClient,
        auth_headers: dict,
    ) -> None:
        resp = client.patch(
            ME_URL,
            json={"name": "New Name"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_admin_updates_preferences(
        self,
        client: TestClient,
        auth_headers: dict,
    ) -> None:
        resp = client.patch(
            ME_URL,
            json={"preferences": {"is_vegetarian": True}},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_non_admin_returns_403(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        other_user: User,
    ) -> None:
        # test_user fixture sets admin_id on test_household
        token = create_access_token(subject=str(other_user.id))
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.patch(
            ME_URL,
            json={"name": "Nope"},
            headers=headers,
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /me/members
# ---------------------------------------------------------------------------


class TestGetMembers:
    def test_returns_members(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        other_user: User,
        auth_headers: dict,
    ) -> None:
        resp = client.get(MEMBERS_URL, headers=auth_headers)
        assert resp.status_code == 200
        members = resp.json()
        ids = {m["id"] for m in members}
        assert str(test_user.id) in ids
        assert str(other_user.id) in ids


# ---------------------------------------------------------------------------
# POST /join
# ---------------------------------------------------------------------------


class TestJoinHousehold:
    def test_valid_invite_code(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        other_household: Household,
        auth_headers: dict,
    ) -> None:
        resp = client.post(
            JOIN_URL,
            json={"invite_code": other_household.invite_code},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == str(other_household.id)

    def test_invalid_invite_code(
        self,
        client: TestClient,
        auth_headers: dict,
    ) -> None:
        resp = client.post(
            JOIN_URL,
            json={"invite_code": "ZZZZZZZZ"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_already_member_is_noop(
        self,
        client: TestClient,
        db_session: Session,
        test_household: Household,
        auth_headers: dict,
    ) -> None:
        resp = client.post(
            JOIN_URL,
            json={"invite_code": test_household.invite_code},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == str(test_household.id)


# ---------------------------------------------------------------------------
# POST /leave
# ---------------------------------------------------------------------------


class TestLeaveHousehold:
    def test_sole_member_stays(
        self,
        client: TestClient,
        auth_headers: dict,
        test_household: Household,
    ) -> None:
        resp = client.post(LEAVE_URL, headers=auth_headers)
        assert resp.status_code == 200
        # Should return the same household (no other members)
        assert resp.json()["id"] == str(test_household.id)

    def test_leaves_creates_private(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        other_user: User,
        test_household: Household,
        auth_headers: dict,
    ) -> None:
        old_hh_id = str(test_household.id)
        user_id = str(test_user.id)
        resp = client.post(LEAVE_URL, headers=auth_headers)
        assert resp.status_code == 200
        new_hh = resp.json()
        assert new_hh["id"] != old_hh_id
        assert new_hh["admin_id"] == user_id


# ---------------------------------------------------------------------------
# DELETE /me/members/{id}
# ---------------------------------------------------------------------------


class TestRemoveMember:
    def test_admin_removes_member(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        other_user: User,
        auth_headers: dict,
    ) -> None:
        resp = client.delete(
            f"{MEMBERS_URL}/{other_user.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

    def test_non_admin_returns_403(
        self,
        client: TestClient,
        db_session: Session,
        other_user: User,
    ) -> None:
        token = create_access_token(subject=str(other_user.id))
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.delete(
            f"{MEMBERS_URL}/{uuid.uuid4()}",
            headers=headers,
        )
        assert resp.status_code == 403

    def test_remove_self_returns_400(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict,
    ) -> None:
        resp = client.delete(
            f"{MEMBERS_URL}/{test_user.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_remove_nonexistent_returns_404(
        self,
        client: TestClient,
        auth_headers: dict,
    ) -> None:
        resp = client.delete(
            f"{MEMBERS_URL}/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert resp.status_code == 404
