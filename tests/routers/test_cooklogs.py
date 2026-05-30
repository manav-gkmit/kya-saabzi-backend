"""Integration tests for /api/v1/cooklogs endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cooklogs import CookLog
from app.models.dishes import Dish
from app.models.households import Household
from app.models.users import User

pytestmark = pytest.mark.asyncio

BASE_URL = "/api/v1/cooklogs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_log(
    db: AsyncSession,
    user: User,
    household: Household,
    dish_name: str = "Test Dish",
) -> CookLog:
    dish = Dish(name=dish_name, household_id=household.id, meal_type="lunch")
    db.add(dish)
    await db.flush()
    log = CookLog(
        user_id=user.id,
        dish_id=dish.id,
        household_id=household.id,
        note="test note",
        rating=4,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


# ---------------------------------------------------------------------------
# GET /api/v1/cooklogs/
# ---------------------------------------------------------------------------


class TestGetCooklogs:
    """Verify cook log listing with auth and soft-delete filtering."""

    async def test_returns_own_logs(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_user: User,
        async_test_household: Household,
        async_auth_headers: dict,
    ) -> None:
        await _seed_log(async_db_session, async_test_user, async_test_household, "Dish A")
        await _seed_log(async_db_session, async_test_user, async_test_household, "Dish B")

        resp = await async_client.get(BASE_URL, headers=async_auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_excludes_deleted(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_user: User,
        async_test_household: Household,
        async_auth_headers: dict,
    ) -> None:
        log = await _seed_log(async_db_session, async_test_user, async_test_household)
        from datetime import datetime

        log.deleted_at = datetime.now(UTC)
        await async_db_session.commit()

        resp = await async_client.get(BASE_URL, headers=async_auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    async def test_isolation_from_other_users(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_user: User,
        async_test_household: Household,
        async_auth_headers: dict,
    ) -> None:
        other_user = User(
            email="other8@example.com",
            username="otheruser8",
            hashed_password="password",
            household_id=async_test_household.id,
        )
        async_db_session.add(other_user)
        await async_db_session.commit()
        await async_db_session.refresh(other_user)

        await _seed_log(async_db_session, other_user, async_test_household, "Other Dish")

        resp = await async_client.get(BASE_URL, headers=async_auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    async def test_pagination(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_user: User,
        async_test_household: Household,
        async_auth_headers: dict,
    ) -> None:
        names = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
        for name in names:
            await _seed_log(async_db_session, async_test_user, async_test_household, name)

        resp = await async_client.get(f"{BASE_URL}?limit=2&offset=0", headers=async_auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2


# ---------------------------------------------------------------------------
# DELETE /api/v1/cooklogs/{id}
# ---------------------------------------------------------------------------


class TestDeleteCooklog:
    """Verify soft-delete with ownership checks."""

    async def test_own_log_soft_deleted(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_user: User,
        async_test_household: Household,
        async_auth_headers: dict,
    ) -> None:
        log = await _seed_log(async_db_session, async_test_user, async_test_household)
        log_id = log.id
        resp = await async_client.delete(f"{BASE_URL}/{log_id}", headers=async_auth_headers)
        assert resp.status_code == 204

        async_db_session.expire_all()
        refreshed = await async_db_session.get(CookLog, log_id)
        assert refreshed is not None
        assert refreshed.deleted_at is not None

    async def test_foreign_log_returns_403(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_user: User,
        async_test_household: Household,
        async_auth_headers: dict,
    ) -> None:
        other_user = User(
            email="other9@example.com",
            username="otheruser9",
            hashed_password="password",
            household_id=async_test_household.id,
        )
        async_db_session.add(other_user)
        await async_db_session.commit()
        await async_db_session.refresh(other_user)

        log = await _seed_log(async_db_session, other_user, async_test_household, "Foreign Dish")
        resp = await async_client.delete(f"{BASE_URL}/{log.id}", headers=async_auth_headers)
        assert resp.status_code == 403

    async def test_not_found(
        self,
        async_client: AsyncClient,
        async_auth_headers: dict,
    ) -> None:
        fake_id = uuid.uuid4()
        resp = await async_client.delete(f"{BASE_URL}/{fake_id}", headers=async_auth_headers)
        assert resp.status_code == 404

    async def test_already_deleted_returns_404(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_user: User,
        async_test_household: Household,
        async_auth_headers: dict,
    ) -> None:
        log = await _seed_log(async_db_session, async_test_user, async_test_household)
        from datetime import datetime

        log.deleted_at = datetime.now(UTC)
        await async_db_session.commit()

        resp = await async_client.delete(f"{BASE_URL}/{log.id}", headers=async_auth_headers)
        assert resp.status_code == 404
