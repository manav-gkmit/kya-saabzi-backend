"""Integration tests for /api/v1/cooklogs endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cooklogs import CookLog
from app.models.dishes import Dish
from app.models.households import Household
from app.models.users import User

BASE_URL = "/api/v1/cooklogs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_log(
    db: Session,
    user: User,
    household: Household,
    dish_name: str = "Test Dish",
) -> CookLog:
    dish = Dish(name=dish_name, household_id=household.id, meal_type="lunch")
    db.add(dish)
    db.flush()
    log = CookLog(
        user_id=user.id,
        dish_id=dish.id,
        household_id=household.id,
        note="test note",
        rating=4,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


# ---------------------------------------------------------------------------
# GET /api/v1/cooklogs/
# ---------------------------------------------------------------------------


class TestGetCooklogs:
    """Verify cook log listing with auth and soft-delete filtering."""

    def test_returns_own_logs(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        test_household: Household,
        auth_headers: dict,
    ) -> None:
        _seed_log(db_session, test_user, test_household, "Dish A")
        _seed_log(db_session, test_user, test_household, "Dish B")

        resp = client.get(BASE_URL, headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_excludes_deleted(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        test_household: Household,
        auth_headers: dict,
    ) -> None:
        log = _seed_log(db_session, test_user, test_household)
        from datetime import datetime

        log.deleted_at = datetime.now(UTC)
        db_session.commit()

        resp = client.get(BASE_URL, headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_isolation_from_other_users(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        other_user: User,
        test_household: Household,
        auth_headers: dict,
    ) -> None:
        _seed_log(db_session, other_user, test_household, "Other Dish")

        resp = client.get(BASE_URL, headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_pagination(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        test_household: Household,
        auth_headers: dict,
    ) -> None:
        names = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
        for name in names:
            _seed_log(db_session, test_user, test_household, name)

        resp = client.get(f"{BASE_URL}?limit=2&offset=0", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2


# ---------------------------------------------------------------------------
# DELETE /api/v1/cooklogs/{id}
# ---------------------------------------------------------------------------


class TestDeleteCooklog:
    """Verify soft-delete with ownership checks."""

    def test_own_log_soft_deleted(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        test_household: Household,
        auth_headers: dict,
    ) -> None:
        log = _seed_log(db_session, test_user, test_household)
        log_id = log.id
        resp = client.delete(f"{BASE_URL}/{log_id}", headers=auth_headers)
        assert resp.status_code == 204

        db_session.expire_all()
        refreshed = db_session.get(CookLog, log_id)
        assert refreshed is not None
        assert refreshed.deleted_at is not None

    def test_foreign_log_returns_403(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        other_user: User,
        test_household: Household,
        auth_headers: dict,
    ) -> None:
        log = _seed_log(db_session, other_user, test_household, "Foreign Dish")
        resp = client.delete(f"{BASE_URL}/{log.id}", headers=auth_headers)
        assert resp.status_code == 403

    def test_not_found(
        self,
        client: TestClient,
        auth_headers: dict,
    ) -> None:
        fake_id = uuid.uuid4()
        resp = client.delete(f"{BASE_URL}/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_already_deleted_returns_404(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        test_household: Household,
        auth_headers: dict,
    ) -> None:
        log = _seed_log(db_session, test_user, test_household)
        from datetime import datetime

        log.deleted_at = datetime.now(UTC)
        db_session.commit()

        resp = client.delete(f"{BASE_URL}/{log.id}", headers=auth_headers)
        assert resp.status_code == 404
