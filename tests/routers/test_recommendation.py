"""Integration tests for /api/v1/recommend endpoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cooklogs import CookLog
from app.models.dishes import Dish
from app.models.households import Household
from app.models.users import User

pytestmark = pytest.mark.asyncio

BASE_URL = "/api/v1/recommend/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_dishes_and_logs(
    db: AsyncSession,
    user: User,
    household: Household,
    count: int = 3,
) -> list[Dish]:
    dishes = []
    names = ["alpha", "beta", "gamma", "delta", "epsilon"]
    for i in range(count):
        dish = Dish(
            name=names[i % len(names)],
            household_id=household.id,
            meal_type="lunch",
        )
        db.add(dish)
        await db.flush()
        log = CookLog(
            user_id=user.id,
            dish_id=dish.id,
            household_id=household.id,
            rating=3 + (i % 3),
        )
        db.add(log)
        dishes.append(dish)
    await db.commit()
    return dishes


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetRecommendation:
    """GET /api/v1/recommend/"""

    @patch("app.services.recommendation.random.uniform", return_value=5.0)
    async def test_returns_recommendations(
        self,
        mock_rand,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_user: User,
        async_test_household: Household,
        async_auth_headers: dict,
    ) -> None:
        # Bypass cooldown so recently-seeded dishes aren't filtered out
        async_test_household.preferences = {"include_recently_cooked": True}
        await async_db_session.commit()

        await _seed_dishes_and_logs(async_db_session, async_test_user, async_test_household, 5)

        resp = await async_client.get(f"{BASE_URL}?meal_type=lunch", headers=async_auth_headers)
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) > 0
        assert "dish" in results[0]
        assert "score_breakdown" in results[0]

    @patch("app.services.recommendation.random.uniform", return_value=5.0)
    async def test_with_explicit_meal_type(
        self,
        mock_rand,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_user: User,
        async_test_household: Household,
        async_auth_headers: dict,
    ) -> None:
        async_test_household.preferences = {"include_recently_cooked": True}
        await async_db_session.commit()

        # Seed dinner dishes
        names = ["tikka", "korma", "biryani"]
        for name in names:
            dish = Dish(name=name, household_id=async_test_household.id, meal_type="dinner")
            async_db_session.add(dish)
            await async_db_session.flush()
            async_db_session.add(
                CookLog(
                    user_id=async_test_user.id,
                    dish_id=dish.id,
                    household_id=async_test_household.id,
                    rating=4,
                )
            )
        await async_db_session.commit()

        resp = await async_client.get(f"{BASE_URL}?meal_type=dinner", headers=async_auth_headers)
        assert resp.status_code == 200

    async def test_no_recommendations_returns_404(
        self,
        async_client: AsyncClient,
        async_auth_headers: dict,
    ) -> None:
        resp = await async_client.get(BASE_URL, headers=async_auth_headers)
        assert resp.status_code == 404

    async def test_unauthenticated(self, async_client: AsyncClient) -> None:
        resp = await async_client.get(BASE_URL)
        assert resp.status_code in (401, 403)
