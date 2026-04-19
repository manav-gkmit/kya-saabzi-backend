"""Integration tests for /api/v1/recommend endpoint."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cooklogs import CookLog
from app.models.dishes import Dish
from app.models.households import Household
from app.models.users import User


BASE_URL = "/api/v1/recommend/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_dishes_and_logs(
    db: Session,
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
        db.flush()
        log = CookLog(
            user_id=user.id,
            dish_id=dish.id,
            household_id=household.id,
            rating=3 + (i % 3),
        )
        db.add(log)
        dishes.append(dish)
    db.commit()
    return dishes


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetRecommendation:
    """GET /api/v1/recommend/"""

    @patch("app.services.recommendation.random.uniform", return_value=5.0)
    def test_returns_recommendations(
        self, mock_rand, client: TestClient, db_session: Session,
        test_user: User, test_household: Household, auth_headers: dict,
    ) -> None:
        # Bypass cooldown so recently-seeded dishes aren't filtered out
        test_household.preferences = {"include_recently_cooked": True}
        db_session.commit()

        _seed_dishes_and_logs(db_session, test_user, test_household, 5)

        resp = client.get(f"{BASE_URL}?meal_type=lunch", headers=auth_headers)
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) > 0
        assert "dish" in results[0]
        assert "score_breakdown" in results[0]

    @patch("app.services.recommendation.random.uniform", return_value=5.0)
    def test_with_explicit_meal_type(
        self, mock_rand, client: TestClient, db_session: Session,
        test_user: User, test_household: Household, auth_headers: dict,
    ) -> None:
        test_household.preferences = {"include_recently_cooked": True}
        db_session.commit()

        # Seed dinner dishes
        names = ["tikka", "korma", "biryani"]
        for name in names:
            dish = Dish(name=name, household_id=test_household.id, meal_type="dinner")
            db_session.add(dish)
            db_session.flush()
            db_session.add(CookLog(
                user_id=test_user.id, dish_id=dish.id,
                household_id=test_household.id, rating=4,
            ))
        db_session.commit()

        resp = client.get(f"{BASE_URL}?meal_type=dinner", headers=auth_headers)
        assert resp.status_code == 200

    def test_no_recommendations_returns_404(
        self, client: TestClient, auth_headers: dict,
    ) -> None:
        resp = client.get(BASE_URL, headers=auth_headers)
        assert resp.status_code == 404

    def test_unauthenticated(self, client: TestClient) -> None:
        resp = client.get(BASE_URL)
        assert resp.status_code in (401, 403)
