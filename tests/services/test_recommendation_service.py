"""Tests for app.services.recommendation — HybridRecoEngine scoring."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cooklogs import CookLog
from app.models.dishes import Dish
from app.models.households import Household
from app.models.users import User
from app.services.recommendation import _DEFAULT_WINDOW_DAYS, HybridRecoEngine

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _dish(
    db: AsyncSession,
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
    await db.flush()
    return d


async def _log(
    db: AsyncSession,
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
    await db.flush()
    if days_ago:
        cl.created_at = datetime.now(UTC) - timedelta(days=days_ago)
        await db.flush()
    return cl


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestHybridRecoEngineInit:
    """Verify engine initialization."""

    async def test_invalid_household_raises(self, async_db_session: AsyncSession) -> None:
        with pytest.raises(ValueError, match="not found"):
            await HybridRecoEngine.create(async_db_session, uuid.uuid4())

    async def test_valid_household_initialises(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        engine = await HybridRecoEngine.create(async_db_session, async_test_household.id)
        assert engine._household_id == async_test_household.id


# ---------------------------------------------------------------------------
# get_top_n
# ---------------------------------------------------------------------------


class TestGetTopN:
    """Verify end-to-end recommendation output."""

    @patch("app.services.recommendation.random.uniform", return_value=5.0)
    async def test_returns_scored_dishes(
        self,
        mock_rand,
        async_db_session: AsyncSession,
        async_test_household: Household,
        async_test_user: User,
    ) -> None:
        await _dish(async_db_session, "dish a", async_test_household.id)
        await _dish(async_db_session, "dish b", async_test_household.id)
        await _dish(async_db_session, "dish c", async_test_household.id)
        await _dish(async_db_session, "dish d", async_test_household.id)
        await async_db_session.commit()

        engine = await HybridRecoEngine.create(async_db_session, async_test_household.id)
        results = await engine.get_top_n("lunch", count=3)

        assert len(results) <= 3
        for r in results:
            assert r.dish is not None
            assert r.score_breakdown is not None

    @patch("app.services.recommendation.random.uniform", return_value=5.0)
    async def test_empty_when_no_candidates(
        self,
        mock_rand,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        engine = await HybridRecoEngine.create(async_db_session, async_test_household.id)
        results = await engine.get_top_n("lunch")
        assert results == []


# ---------------------------------------------------------------------------
# _fetch_candidates
# ---------------------------------------------------------------------------


class TestFetchCandidates:
    """Verify candidate filtering."""

    async def test_filters_by_meal_type(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        await _dish(async_db_session, "lunch dish", async_test_household.id, meal_type="lunch")
        await _dish(async_db_session, "dinner dish", async_test_household.id, meal_type="dinner")
        await async_db_session.commit()

        engine = await HybridRecoEngine.create(async_db_session, async_test_household.id)
        candidates = await engine._fetch_candidates("lunch")
        assert all(c.meal_type == "lunch" for c in candidates)

    async def test_deduplicates_household_over_global(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        await _dish(async_db_session, "dal fry", household_id=None, meal_type="lunch")
        await _dish(async_db_session, "Dal Fry", async_test_household.id, meal_type="lunch")
        await async_db_session.commit()

        engine = await HybridRecoEngine.create(async_db_session, async_test_household.id)
        candidates = await engine._fetch_candidates("lunch")

        dal_candidates = [c for c in candidates if c.name.lower() == "dal fry"]
        assert len(dal_candidates) == 1
        assert dal_candidates[0].household_id == async_test_household.id

    async def test_vegetarian_filter(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        async_test_household.preferences = {"is_vegetarian": True}
        await async_db_session.commit()

        await _dish(async_db_session, "paneer", async_test_household.id, dish_type="veg")
        await _dish(async_db_session, "chicken", async_test_household.id, dish_type="non-veg")
        await _dish(async_db_session, "tofu", async_test_household.id, dish_type="vegan")
        await async_db_session.commit()

        engine = await HybridRecoEngine.create(async_db_session, async_test_household.id)
        candidates = await engine._fetch_candidates("lunch")

        names = {c.name for c in candidates}
        assert "chicken" not in names
        assert "paneer" in names
        assert "tofu" in names


# ---------------------------------------------------------------------------
# _apply_cooldown
# ---------------------------------------------------------------------------


class TestApplyCooldown:
    """Verify recently-cooked exclusion."""

    async def test_excludes_recently_cooked(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
        async_test_user: User,
    ) -> None:
        d1 = await _dish(async_db_session, "recent dish", async_test_household.id)
        d2 = await _dish(async_db_session, "old dish", async_test_household.id)
        await _log(async_db_session, async_test_household.id, async_test_user.id, d1.id, days_ago=1)
        await _log(async_db_session, async_test_household.id, async_test_user.id, d2.id, days_ago=30)
        await async_db_session.commit()

        engine = await HybridRecoEngine.create(async_db_session, async_test_household.id)
        filtered = await engine._apply_cooldown([d1, d2])

        ids = {d.id for d in filtered}
        assert d1.id not in ids
        assert d2.id in ids

    async def test_include_recently_cooked_skips_filter(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
        async_test_user: User,
    ) -> None:
        async_test_household.preferences = {"include_recently_cooked": True}
        await async_db_session.commit()

        d1 = await _dish(async_db_session, "recent dish", async_test_household.id)
        await _log(async_db_session, async_test_household.id, async_test_user.id, d1.id, days_ago=0)
        await async_db_session.commit()

        engine = await HybridRecoEngine.create(async_db_session, async_test_household.id)
        filtered = await engine._apply_cooldown([d1])
        assert len(filtered) == 1


# ---------------------------------------------------------------------------
# _score_all
# ---------------------------------------------------------------------------


class TestScoreAll:
    """Verify scoring mechanics."""

    async def test_empty_list_returns_empty(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        engine = await HybridRecoEngine.create(async_db_session, async_test_household.id)
        assert await engine._score_all([]) == []

    @patch("app.services.recommendation.random.uniform", return_value=0.0)
    async def test_higher_rated_dish_scores_higher(
        self,
        mock_rand,
        async_db_session: AsyncSession,
        async_test_household: Household,
        async_test_user: User,
    ) -> None:
        d1 = await _dish(async_db_session, "loved dish", async_test_household.id)
        d2 = await _dish(async_db_session, "meh dish", async_test_household.id)
        await _log(async_db_session, async_test_household.id, async_test_user.id, d1.id, rating=5)
        await _log(async_db_session, async_test_household.id, async_test_user.id, d2.id, rating=1)
        await async_db_session.commit()

        engine = await HybridRecoEngine.create(async_db_session, async_test_household.id)
        scored = await engine._score_all([d1, d2])

        # First item should be the higher-rated dish
        assert scored[0][0].id == d1.id
        assert scored[0][1]["total"] > scored[1][1]["total"]


# ---------------------------------------------------------------------------
# _build_results
# ---------------------------------------------------------------------------


class TestBuildResults:
    """Verify result assembly with notes."""

    async def test_notes_fetched_max_three(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
        async_test_user: User,
    ) -> None:
        d = await _dish(async_db_session, "noted dish", async_test_household.id)
        for i in range(5):
            await _log(
                async_db_session,
                async_test_household.id,
                async_test_user.id,
                d.id,
                note=f"note {i}",
            )
        await async_db_session.commit()

        engine = await HybridRecoEngine.create(async_db_session, async_test_household.id)
        breakdown = {"popularity": 1.0, "history": 1.0, "randomness": 1.0, "total": 3.0}
        results = await engine._build_results([(d, breakdown)])

        assert len(results) == 1
        assert len(results[0].notes) <= 3


# ---------------------------------------------------------------------------
# _safe_window
# ---------------------------------------------------------------------------


class TestSafeWindow:
    """Verify preference window parsing."""

    async def test_valid_int(self) -> None:
        assert HybridRecoEngine._safe_window({"recommendation_window_days": 10}) == 10

    async def test_negative_clamped_to_zero(self) -> None:
        assert HybridRecoEngine._safe_window({"recommendation_window_days": -5}) == 0

    async def test_invalid_string_returns_default(self) -> None:
        assert (
            HybridRecoEngine._safe_window({"recommendation_window_days": "abc"})
            == _DEFAULT_WINDOW_DAYS
        )

    async def test_missing_key_returns_default(self) -> None:
        assert HybridRecoEngine._safe_window({}) == _DEFAULT_WINDOW_DAYS

    async def test_none_value_returns_default(self) -> None:
        assert (
            HybridRecoEngine._safe_window({"recommendation_window_days": None})
            == _DEFAULT_WINDOW_DAYS
        )
