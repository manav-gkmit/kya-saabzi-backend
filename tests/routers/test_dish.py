"""Integration tests for /api/v1/dishes endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.dishes import Dish
from app.models.households import Household
from app.models.users import User


CREATE_URL = "/api/v1/dishes/"
SEARCH_URL = "/api/v1/dishes/search"


# ---------------------------------------------------------------------------
# POST /api/v1/dishes/
# ---------------------------------------------------------------------------


class TestCreateDish:
    """Verify dish creation (find-or-create) with cook log recording."""

    def test_creates_new_dish(
        self, client: TestClient, auth_headers: dict,
    ) -> None:
        resp = client.post(
            CREATE_URL,
            json={"name": "Palak Paneer"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "palak paneer"
        assert "id" in body

    def test_existing_dish_returns_same(
        self, client: TestClient, auth_headers: dict,
    ) -> None:
        resp1 = client.post(
            CREATE_URL,
            json={"name": "Dal Makhani"},
            headers=auth_headers,
        )
        resp2 = client.post(
            CREATE_URL,
            json={"name": "dal makhani"},
            headers=auth_headers,
        )
        assert resp1.json()["id"] == resp2.json()["id"]

    def test_with_optional_fields(
        self, client: TestClient, auth_headers: dict,
    ) -> None:
        resp = client.post(
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
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["dish_type"] == "non-veg"
        assert body["spiciness"] == 4

    def test_unauthenticated(self, client: TestClient) -> None:
        resp = client.post(CREATE_URL, json={"name": "Nope"})
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/v1/dishes/search
# ---------------------------------------------------------------------------


class TestSearchDishes:
    """Verify dish search with ILIKE + fuzzy fallback."""

    def test_returns_matches(
        self, client: TestClient, db_session: Session,
        test_household: Household, auth_headers: dict,
    ) -> None:
        db_session.add(Dish(name="chole bhature", household_id=test_household.id, meal_type="lunch"))
        db_session.add(Dish(name="chole masala", household_id=test_household.id, meal_type="lunch"))
        db_session.commit()

        resp = client.get(f"{SEARCH_URL}?q=chole", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_short_query_returns_empty(
        self, client: TestClient, auth_headers: dict,
    ) -> None:
        resp = client.get(f"{SEARCH_URL}?q=da", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_no_matches_returns_empty(
        self, client: TestClient, auth_headers: dict,
    ) -> None:
        resp = client.get(f"{SEARCH_URL}?q=zzzzzzz", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_other_household_excluded(
        self, client: TestClient, db_session: Session,
        other_household: Household, auth_headers: dict,
    ) -> None:
        db_session.add(Dish(name="secret dish", household_id=other_household.id, meal_type="lunch"))
        db_session.commit()

        resp = client.get(f"{SEARCH_URL}?q=secret", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_pagination(
        self, client: TestClient, db_session: Session,
        test_household: Household, auth_headers: dict,
    ) -> None:
        for i in range(5):
            db_session.add(Dish(name=f"paneer dish {i}", household_id=test_household.id, meal_type="lunch"))
        db_session.commit()

        resp = client.get(f"{SEARCH_URL}?q=paneer&limit=2", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2
