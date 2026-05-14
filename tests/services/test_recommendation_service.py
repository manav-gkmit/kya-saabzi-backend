"""Tests for app.services.recommendation — HybridRecoEngine scoring."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.cooklogs import CookLog
from app.models.dishes import Dish
from app.models.households import Household
from app.models.users import User
from app.services.recommendation import _DEFAULT_WINDOW_DAYS, HybridRecoEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dish(
    db: Session,
    name: str,
    household_id: uuid.UUID | None,
    meal_type: str = "lunch",
    dish_type: str = "veg",
) -> Dish:
    d = Dish(
        name=name,
        household_id=household_id,
        meal_type=meal_type,
        dish_type=dish_type,
    )
    db.add(d)
    db.flush()
    return d


def _log(
    db: Session,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    dish_id: uuid.UUID,
    *,
    note: str | None = None,
    rating: int | None = None,
    days_ago: int = 0,
) -> CookLog:
    cl = CookLog(
        household_id=household_id,
        user_id=user_id,
        dish_id=dish_id,
        note=note,
        rating=rating,
    )
    db.add(cl)
    db.flush()
    if days_ago:
        cl.created_at = datetime.now(UTC) - timedelta(days=days_ago)
        db.flush()
    return cl


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestHybridRecoEngineInit:
    """Verify engine initialization."""

    def test_invalid_household_raises(self, db_session: Session) -> None:
        with pytest.raises(ValueError, match="not found"):
            HybridRecoEngine(db_session, uuid.uuid4())

    def test_valid_household_initialises(
        self,
        db_session: Session,
        test_household: Household,
    ) -> None:
        engine = HybridRecoEngine(db_session, test_household.id)
        assert engine._household_id == test_household.id


# ---------------------------------------------------------------------------
# get_top_n
# ---------------------------------------------------------------------------


class TestGetTopN:
    """Verify end-to-end recommendation output."""

    @patch("app.services.recommendation.random.uniform", return_value=5.0)
    def test_returns_scored_dishes(
        self,
        mock_rand,
        db_session: Session,
        test_household: Household,
        test_user: User,
    ) -> None:
        _dish(db_session, "dish a", test_household.id)
        _dish(db_session, "dish b", test_household.id)
        _dish(db_session, "dish c", test_household.id)
        _dish(db_session, "dish d", test_household.id)
        db_session.commit()

        engine = HybridRecoEngine(db_session, test_household.id)
        results = engine.get_top_n("lunch", count=3)

        assert len(results) <= 3
        for r in results:
            assert r.dish is not None
            assert r.score_breakdown is not None

    @patch("app.services.recommendation.random.uniform", return_value=5.0)
    def test_empty_when_no_candidates(
        self,
        mock_rand,
        db_session: Session,
        test_household: Household,
    ) -> None:
        engine = HybridRecoEngine(db_session, test_household.id)
        results = engine.get_top_n("lunch")
        assert results == []


# ---------------------------------------------------------------------------
# _fetch_candidates
# ---------------------------------------------------------------------------


class TestFetchCandidates:
    """Verify candidate filtering."""

    def test_filters_by_meal_type(
        self,
        db_session: Session,
        test_household: Household,
    ) -> None:
        _dish(db_session, "lunch dish", test_household.id, meal_type="lunch")
        _dish(db_session, "dinner dish", test_household.id, meal_type="dinner")
        db_session.commit()

        engine = HybridRecoEngine(db_session, test_household.id)
        candidates = engine._fetch_candidates("lunch")
        assert all(c.meal_type == "lunch" for c in candidates)

    def test_deduplicates_household_over_global(
        self,
        db_session: Session,
        test_household: Household,
    ) -> None:
        _dish(db_session, "dal fry", household_id=None, meal_type="lunch")
        _dish(db_session, "Dal Fry", test_household.id, meal_type="lunch")
        db_session.commit()

        engine = HybridRecoEngine(db_session, test_household.id)
        candidates = engine._fetch_candidates("lunch")

        dal_candidates = [c for c in candidates if c.name.lower() == "dal fry"]
        assert len(dal_candidates) == 1
        assert dal_candidates[0].household_id == test_household.id

    def test_vegetarian_filter(
        self,
        db_session: Session,
        test_household: Household,
    ) -> None:
        test_household.preferences = {"is_vegetarian": True}
        db_session.commit()

        _dish(db_session, "paneer", test_household.id, dish_type="veg")
        _dish(db_session, "chicken", test_household.id, dish_type="non-veg")
        _dish(db_session, "tofu", test_household.id, dish_type="vegan")
        db_session.commit()

        engine = HybridRecoEngine(db_session, test_household.id)
        candidates = engine._fetch_candidates("lunch")

        names = {c.name for c in candidates}
        assert "chicken" not in names
        assert "paneer" in names
        assert "tofu" in names


# ---------------------------------------------------------------------------
# _apply_cooldown
# ---------------------------------------------------------------------------


class TestApplyCooldown:
    """Verify recently-cooked exclusion."""

    def test_excludes_recently_cooked(
        self,
        db_session: Session,
        test_household: Household,
        test_user: User,
    ) -> None:
        d1 = _dish(db_session, "recent dish", test_household.id)
        d2 = _dish(db_session, "old dish", test_household.id)
        _log(db_session, test_household.id, test_user.id, d1.id, days_ago=1)
        _log(db_session, test_household.id, test_user.id, d2.id, days_ago=30)
        db_session.commit()

        engine = HybridRecoEngine(db_session, test_household.id)
        filtered = engine._apply_cooldown([d1, d2])

        ids = {d.id for d in filtered}
        assert d1.id not in ids
        assert d2.id in ids

    def test_include_recently_cooked_skips_filter(
        self,
        db_session: Session,
        test_household: Household,
        test_user: User,
    ) -> None:
        test_household.preferences = {"include_recently_cooked": True}
        db_session.commit()

        d1 = _dish(db_session, "recent dish", test_household.id)
        _log(db_session, test_household.id, test_user.id, d1.id, days_ago=0)
        db_session.commit()

        engine = HybridRecoEngine(db_session, test_household.id)
        filtered = engine._apply_cooldown([d1])
        assert len(filtered) == 1


# ---------------------------------------------------------------------------
# _score_all
# ---------------------------------------------------------------------------


class TestScoreAll:
    """Verify scoring mechanics."""

    def test_empty_list_returns_empty(
        self,
        db_session: Session,
        test_household: Household,
    ) -> None:
        engine = HybridRecoEngine(db_session, test_household.id)
        assert engine._score_all([]) == []

    @patch("app.services.recommendation.random.uniform", return_value=0.0)
    def test_higher_rated_dish_scores_higher(
        self,
        mock_rand,
        db_session: Session,
        test_household: Household,
        test_user: User,
    ) -> None:
        d1 = _dish(db_session, "loved dish", test_household.id)
        d2 = _dish(db_session, "meh dish", test_household.id)
        _log(db_session, test_household.id, test_user.id, d1.id, rating=5)
        _log(db_session, test_household.id, test_user.id, d2.id, rating=1)
        db_session.commit()

        engine = HybridRecoEngine(db_session, test_household.id)
        scored = engine._score_all([d1, d2])

        # First item should be the higher-rated dish
        assert scored[0][0].id == d1.id
        assert scored[0][1]["total"] > scored[1][1]["total"]


# ---------------------------------------------------------------------------
# _build_results
# ---------------------------------------------------------------------------


class TestBuildResults:
    """Verify result assembly with notes."""

    def test_notes_fetched_max_three(
        self,
        db_session: Session,
        test_household: Household,
        test_user: User,
    ) -> None:
        d = _dish(db_session, "noted dish", test_household.id)
        for i in range(5):
            _log(
                db_session,
                test_household.id,
                test_user.id,
                d.id,
                note=f"note {i}",
            )
        db_session.commit()

        engine = HybridRecoEngine(db_session, test_household.id)
        breakdown = {"popularity": 1.0, "history": 1.0, "randomness": 1.0, "total": 3.0}
        results = engine._build_results([(d, breakdown)])

        assert len(results) == 1
        assert len(results[0].notes) <= 3


# ---------------------------------------------------------------------------
# _safe_window
# ---------------------------------------------------------------------------


class TestSafeWindow:
    """Verify preference window parsing."""

    def test_valid_int(self) -> None:
        assert HybridRecoEngine._safe_window({"recommendation_window_days": 10}) == 10

    def test_negative_clamped_to_zero(self) -> None:
        assert HybridRecoEngine._safe_window({"recommendation_window_days": -5}) == 0

    def test_invalid_string_returns_default(self) -> None:
        assert (
            HybridRecoEngine._safe_window({"recommendation_window_days": "abc"})
            == _DEFAULT_WINDOW_DAYS
        )

    def test_missing_key_returns_default(self) -> None:
        assert HybridRecoEngine._safe_window({}) == _DEFAULT_WINDOW_DAYS

    def test_none_value_returns_default(self) -> None:
        assert (
            HybridRecoEngine._safe_window({"recommendation_window_days": None})
            == _DEFAULT_WINDOW_DAYS
        )
