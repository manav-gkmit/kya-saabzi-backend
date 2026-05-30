"""Tests for app.services.dish — search, find-or-create, cook log creation."""

from __future__ import annotations

from unittest.mock import MagicMock, AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dishes import Dish, Ingredient
from app.models.households import Household
from app.models.users import User
from app.services.dish import (
    _attach_ingredients_to_dish,
    create_cook_log,
    enrich_dish_background_task,
    find_or_create_dish,
    search_dishes,
)

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_dish(
    db: AsyncSession,
    name: str,
    household_id: UUID | None = None,
    meal_type: str = "lunch",
) -> Dish:
    dish = Dish(name=name, household_id=household_id, meal_type=meal_type)
    db.add(dish)
    await db.flush()
    return dish


# ---------------------------------------------------------------------------
# search_dishes
# ---------------------------------------------------------------------------


class TestSearchDishes:
    """Verify ILIKE + difflib fallback search pipeline."""

    async def test_ilike_match_returns_results(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        await _seed_dish(async_db_session, "dal makhani", async_test_household.id)
        await _seed_dish(async_db_session, "dal tadka", async_test_household.id)
        await async_db_session.commit()

        results = await search_dishes(async_db_session, "dal", household_id=async_test_household.id)
        assert len(results) == 2
        assert all(r["similarity"] > 0.4 for r in results)

    async def test_results_sorted_by_similarity(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        await _seed_dish(async_db_session, "palak paneer", async_test_household.id)
        await _seed_dish(async_db_session, "paneer butter masala", async_test_household.id)
        await async_db_session.commit()

        results = await search_dishes(
            async_db_session, "paneer", household_id=async_test_household.id
        )
        if len(results) > 1:
            assert results[0]["similarity"] >= results[1]["similarity"]

    async def test_low_similarity_filtered_out(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        await _seed_dish(async_db_session, "aloo gobi", async_test_household.id)
        await async_db_session.commit()

        results = await search_dishes(
            async_db_session, "zzzzz", household_id=async_test_household.id
        )
        assert len(results) == 0

    async def test_household_scope_includes_global(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        """Global dishes (household_id=None) should be visible."""
        await _seed_dish(async_db_session, "chole bhature", household_id=None)
        await _seed_dish(async_db_session, "chole masala", async_test_household.id)
        await async_db_session.commit()

        results = await search_dishes(
            async_db_session, "chole", household_id=async_test_household.id
        )
        assert len(results) == 2

    async def test_other_household_dishes_excluded(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
        other_household: Household,  # we'll use a mocked other async household or just seed one
    ) -> None:
        household2 = Household(name="Other Home")
        async_db_session.add(household2)
        await async_db_session.commit()
        await _seed_dish(async_db_session, "biryani", household2.id)
        await async_db_session.commit()

        results = await search_dishes(
            async_db_session, "biryani", household_id=async_test_household.id
        )
        assert len(results) == 0

    async def test_pagination_limit(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        for i in range(5):
            await _seed_dish(async_db_session, f"dish {i}", async_test_household.id)
        await async_db_session.commit()

        results = await search_dishes(
            async_db_session,
            "dish",
            household_id=async_test_household.id,
            limit=2,
        )
        assert len(results) == 2

    async def test_pagination_offset(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        for i in range(5):
            await _seed_dish(async_db_session, f"dish {i}", async_test_household.id)
        await async_db_session.commit()

        all_results = await search_dishes(
            async_db_session,
            "dish",
            household_id=async_test_household.id,
            limit=10,
        )
        offset_results = await search_dishes(
            async_db_session,
            "dish",
            household_id=async_test_household.id,
            limit=10,
            offset=2,
        )
        assert len(offset_results) == len(all_results) - 2


# ---------------------------------------------------------------------------
# find_or_create_dish
# ---------------------------------------------------------------------------


class TestFindOrCreateDish:
    """Verify exact-match → fuzzy-match → create pipeline."""

    async def test_exact_match_returns_existing(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        existing = await _seed_dish(async_db_session, "rajma chawal", async_test_household.id)
        await async_db_session.commit()

        result = await find_or_create_dish(
            async_db_session,
            "Rajma Chawal",
            household_id=async_test_household.id,
        )
        assert result.id == existing.id

    async def test_fuzzy_match_corrects_typo(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        existing = await _seed_dish(async_db_session, "palak paneer", async_test_household.id)
        await async_db_session.commit()

        result = await find_or_create_dish(
            async_db_session,
            "palak paner",
            household_id=async_test_household.id,
        )
        assert result.id == existing.id

    async def test_no_match_creates_new(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        result = await find_or_create_dish(
            async_db_session,
            "unique new dish",
            household_id=async_test_household.id,
        )
        await async_db_session.commit()

        assert result.name == "unique new dish"
        fetched = await async_db_session.get(Dish, result.id)
        assert fetched is not None

    async def test_household_dish_shadows_global(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        await _seed_dish(async_db_session, "dal fry", household_id=None)
        hh_dish = await _seed_dish(async_db_session, "dal fry", async_test_household.id)
        await async_db_session.commit()

        result = await find_or_create_dish(
            async_db_session,
            "dal fry",
            household_id=async_test_household.id,
        )
        assert result.id == hh_dish.id

    @patch("app.services.dish.get_current_meal_type", return_value="dinner")
    async def test_defaults_meal_type_from_time(
        self,
        mock_meal,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        result = await find_or_create_dish(
            async_db_session,
            "brand new dish",
            household_id=async_test_household.id,
        )
        await async_db_session.commit()
        assert result.meal_type == "dinner"

    async def test_explicit_meal_type_used(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        result = await find_or_create_dish(
            async_db_session,
            "breakfast item",
            household_id=async_test_household.id,
            meal_type="breakfast",
        )
        await async_db_session.commit()
        assert result.meal_type == "breakfast"

    async def test_optional_fields_applied(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        result = await find_or_create_dish(
            async_db_session,
            "spicy thing",
            household_id=async_test_household.id,
            dish_type="non-veg",
            spiciness=4,
            prep_time_minutes=45,
            calories_estimate=500,
        )
        await async_db_session.commit()
        assert result.dish_type == "non-veg"
        assert result.spiciness == 4
        assert result.prep_time_minutes == 45
        assert result.calories_estimate == 500


# ---------------------------------------------------------------------------
# create_cook_log
# ---------------------------------------------------------------------------


class TestCreateCookLog:
    """Verify cook log persistence."""

    async def test_creates_log_with_all_fields(
        self,
        async_db_session: AsyncSession,
        async_test_user: User,
        async_test_household: Household,
    ) -> None:
        dish = await _seed_dish(async_db_session, "test dish", async_test_household.id)
        await async_db_session.commit()

        log = await create_cook_log(
            async_db_session,
            household_id=async_test_household.id,
            user_id=async_test_user.id,
            dish_id=dish.id,
            note="delicious",
            rating=5,
        )
        await async_db_session.commit()

        assert log.user_id == async_test_user.id
        assert log.dish_id == dish.id
        assert log.note == "delicious"
        assert log.rating == 5

    async def test_optional_fields_nullable(
        self,
        async_db_session: AsyncSession,
        async_test_user: User,
        async_test_household: Household,
    ) -> None:
        dish = await _seed_dish(async_db_session, "basic dish", async_test_household.id)
        await async_db_session.commit()

        log = await create_cook_log(
            async_db_session,
            household_id=async_test_household.id,
            user_id=async_test_user.id,
            dish_id=dish.id,
        )
        await async_db_session.commit()

        assert log.note is None
        assert log.rating is None

    async def test_flush_without_commit(
        self,
        async_db_session: AsyncSession,
        async_test_user: User,
        async_test_household: Household,
    ) -> None:
        """create_cook_log only flushes — caller is responsible for commit."""
        dish = await _seed_dish(async_db_session, "flush test", async_test_household.id)
        await async_db_session.commit()

        log = await create_cook_log(
            async_db_session,
            household_id=async_test_household.id,
            user_id=async_test_user.id,
            dish_id=dish.id,
        )
        # Log has an ID (flushed) even without commit
        assert log.id is not None


# ---------------------------------------------------------------------------
# _attach_ingredients_to_dish
# ---------------------------------------------------------------------------


class TestAttachIngredients:
    """Verify ingredient creation and attachment logic."""

    async def test_creates_new_ingredients(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        dish = await _seed_dish(async_db_session, "test dish", async_test_household.id)
        await async_db_session.commit()

        await _attach_ingredients_to_dish(async_db_session, dish, ["Spinach", "Paneer"])
        await async_db_session.commit()

        # ingredients are eagerly refreshed or we can use async fetch if needed
        # but _attach... does it synchronously for the list
        names = {ing.name for ing in dish.ingredients}
        assert names == {"spinach", "paneer"}

    async def test_reuses_existing_ingredients(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        existing = Ingredient(name="garlic")
        async_db_session.add(existing)
        dish = await _seed_dish(async_db_session, "garlic dish", async_test_household.id)
        await async_db_session.commit()

        await _attach_ingredients_to_dish(async_db_session, dish, ["Garlic"])
        await async_db_session.commit()

        assert len(dish.ingredients) == 1
        assert dish.ingredients[0].id == existing.id

    async def test_no_duplicates_on_repeated_call(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        dish = await _seed_dish(async_db_session, "dup dish", async_test_household.id)
        await async_db_session.commit()

        await _attach_ingredients_to_dish(async_db_session, dish, ["tomato"])
        await async_db_session.commit()
        await _attach_ingredients_to_dish(async_db_session, dish, ["tomato"])
        await async_db_session.commit()

        assert len(dish.ingredients) == 1

    async def test_empty_list_is_noop(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        dish = await _seed_dish(async_db_session, "empty dish", async_test_household.id)
        await async_db_session.commit()

        await _attach_ingredients_to_dish(async_db_session, dish, [])
        await async_db_session.commit()

        assert dish.ingredients == []


# ---------------------------------------------------------------------------
# enrich_dish_background_task
# ---------------------------------------------------------------------------


class TestEnrichDishBackgroundTask:
    """Verify background enrichment task behaviour."""

    async def test_skips_nonexistent_dish(self) -> None:
        import uuid

        with patch("app.services.dish.enrichment.SessionLocal") as mock_session_cls:
            mock_db = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_db
            mock_db.get.return_value = None
            await enrich_dish_background_task(uuid.uuid4())
            mock_db.commit.assert_not_called()

    async def test_skips_fully_enriched_dish(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        dish = await _seed_dish(async_db_session, "full dish", async_test_household.id)
        ing = Ingredient(name="onion")
        async_db_session.add(ing)
        await async_db_session.flush()
        dish.ingredients.append(ing)
        dish.calories_estimate = 300
        dish.prep_time_minutes = 20
        await async_db_session.commit()

        with patch("app.services.dish.enrichment.SessionLocal") as mock_session_cls:
            mock_db = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_db
            mock_db.get.return_value = dish
            with patch("app.services.dish.enrichment.enrich_dish_with_gemini") as mock_llm:
                await enrich_dish_background_task(dish.id)
                mock_llm.assert_not_called()

    async def test_enriches_dish_when_data_missing(
        self,
        async_db_session: AsyncSession,
        async_test_household: Household,
    ) -> None:
        dish = await _seed_dish(async_db_session, "bare dish", async_test_household.id)
        await async_db_session.commit()

        from app.services.llm import DishEnrichmentResult

        mock_result = DishEnrichmentResult(
            ingredients=["potato", "oil"],
            prep_time_minutes=15,
            calories_estimate=200,
        )

        with patch("app.services.dish.AsyncSessionLocal") as mock_session_cls:
            mock_db = AsyncMock(spec=AsyncSession)
            mock_session_cls.return_value.__aenter__.return_value = mock_db
            mock_db.get.return_value = dish
            with (
                patch("app.services.dish.enrichment.enrich_dish_with_gemini", return_value=mock_result),
                patch("app.services.dish.enrichment.attach_ingredients_to_dish", new_callable=AsyncMock) as mock_attach,
            ):
                await enrich_dish_background_task(dish.id)
                mock_attach.assert_awaited_once()
                assert dish.calories_estimate == 200
                assert dish.prep_time_minutes == 15
                mock_db.commit.assert_awaited_once()

    async def test_rolls_back_on_exception(self) -> None:
        import uuid

        with patch("app.services.dish.enrichment.SessionLocal") as mock_session_cls:
            mock_db = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_db
            mock_db.get.side_effect = Exception("db error")
            await enrich_dish_background_task(uuid.uuid4())
            mock_db.rollback.assert_awaited_once()
