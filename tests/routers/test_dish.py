"""Integration tests for /api/v1/dishes endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dishes import Dish
from app.models.households import Household

pytestmark = pytest.mark.asyncio

CREATE_URL = "/api/v1/dishes/"
SEARCH_URL = "/api/v1/dishes/search"


# ---------------------------------------------------------------------------
# POST /api/v1/dishes/
# ---------------------------------------------------------------------------


class TestCreateDish:
    """Verify dish creation (find-or-create) with cook log recording."""

    async def test_creates_new_dish(
        self,
        async_client: AsyncClient,
        async_auth_headers: dict,
    ) -> None:
        resp = await async_client.post(
            CREATE_URL,
            json={"name": "Palak Paneer"},
            headers=async_auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "palak paneer"
        assert "id" in body

    async def test_existing_dish_returns_same(
        self,
        async_client: AsyncClient,
        async_auth_headers: dict,
    ) -> None:
        resp1 = await async_client.post(
            CREATE_URL,
            json={"name": "Dal Makhani"},
            headers=async_auth_headers,
        )
        resp2 = await async_client.post(
            CREATE_URL,
            json={"name": "dal makhani"},
            headers=async_auth_headers,
        )
        assert resp1.json()["id"] == resp2.json()["id"]

    async def test_with_optional_fields(
        self,
        async_client: AsyncClient,
        async_auth_headers: dict,
    ) -> None:
        resp = await async_client.post(
            CREATE_URL,
            json={
                "name": "Chicken Biryani",
                "dish_type": "non-veg",
                "meal_type": "dinner",
                "spiciness": 4,
                "rating": 5,
                "note": "Really tasty",
                "prep_time_minutes": 60,
            },
            headers=async_auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["dish_type"] == "non-veg"
        assert body["spiciness"] == 4

    async def test_unauthenticated(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(CREATE_URL, json={"name": "Nope"})
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/v1/dishes/search
# ---------------------------------------------------------------------------


class TestSearchDishes:
    """Verify dish search with ILIKE + fuzzy fallback."""

    async def test_returns_matches(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_household: Household,
        async_auth_headers: dict,
    ) -> None:
        async_db_session.add(
            Dish(name="chole bhature", household_id=async_test_household.id, meal_type="lunch")
        )
        async_db_session.add(Dish(name="chole masala", household_id=async_test_household.id, meal_type="lunch"))
        await async_db_session.commit()

        resp = await async_client.get(f"{SEARCH_URL}?q=chole", headers=async_auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_short_query_returns_empty(
        self,
        async_client: AsyncClient,
        async_auth_headers: dict,
    ) -> None:
        resp = await async_client.get(f"{SEARCH_URL}?q=da", headers=async_auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_no_matches_returns_empty(
        self,
        async_client: AsyncClient,
        async_auth_headers: dict,
    ) -> None:
        resp = await async_client.get(f"{SEARCH_URL}?q=zzzzzzz", headers=async_auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_other_household_excluded(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_auth_headers: dict,
    ) -> None:
        other_household = Household(name="Other Household")
        async_db_session.add(other_household)
        await async_db_session.commit()
        await async_db_session.refresh(other_household)

        async_db_session.add(Dish(name="secret dish", household_id=other_household.id, meal_type="lunch"))
        await async_db_session.commit()

        resp = await async_client.get(f"{SEARCH_URL}?q=secret", headers=async_auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_pagination(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        async_test_household: Household,
        async_auth_headers: dict,
    ) -> None:
        for i in range(5):
            async_db_session.add(
                Dish(name=f"paneer dish {i}", household_id=async_test_household.id, meal_type="lunch")
            )
        await async_db_session.commit()

        resp = await async_client.get(f"{SEARCH_URL}?q=paneer&limit=2", headers=async_auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2
