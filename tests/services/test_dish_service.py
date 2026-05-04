"""Tests for app.services.dish — search, find-or-create, cook log creation."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.models.cooklogs import CookLog
from app.models.dishes import Dish, Ingredient
from app.models.households import Household
from app.models.users import User
from app.services.dish import (
    _attach_ingredients_to_dish,
    _enrich_dish_sync,
    create_cook_log,
    enrich_dish_background_task,
    find_or_create_dish,
    search_dishes,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_dish(
    db: Session,
    name: str,
    household_id: UUID | None = None,
    meal_type: str = "lunch",
) -> Dish:
    dish = Dish(name=name, household_id=household_id, meal_type=meal_type)
    db.add(dish)
    db.flush()
    return dish


# ---------------------------------------------------------------------------
# search_dishes
# ---------------------------------------------------------------------------


class TestSearchDishes:
    """Verify ILIKE + difflib fallback search pipeline."""

    def test_ilike_match_returns_results(
        self, db_session: Session, test_household: Household,
    ) -> None:
        _seed_dish(db_session, "dal makhani", test_household.id)
        _seed_dish(db_session, "dal tadka", test_household.id)
        db_session.commit()

        results = search_dishes(db_session, "dal", household_id=test_household.id)
        assert len(results) == 2
        assert all(r["similarity"] > 0.4 for r in results)

    def test_results_sorted_by_similarity(
        self, db_session: Session, test_household: Household,
    ) -> None:
        _seed_dish(db_session, "palak paneer", test_household.id)
        _seed_dish(db_session, "paneer butter masala", test_household.id)
        db_session.commit()

        results = search_dishes(db_session, "paneer", household_id=test_household.id)
        if len(results) > 1:
            assert results[0]["similarity"] >= results[1]["similarity"]

    def test_low_similarity_filtered_out(
        self, db_session: Session, test_household: Household,
    ) -> None:
        _seed_dish(db_session, "aloo gobi", test_household.id)
        db_session.commit()

        results = search_dishes(db_session, "zzzzz", household_id=test_household.id)
        assert len(results) == 0

    def test_household_scope_includes_global(
        self, db_session: Session, test_household: Household,
    ) -> None:
        """Global dishes (household_id=None) should be visible."""
        _seed_dish(db_session, "chole bhature", household_id=None)
        _seed_dish(db_session, "chole masala", test_household.id)
        db_session.commit()

        results = search_dishes(db_session, "chole", household_id=test_household.id)
        assert len(results) == 2

    def test_other_household_dishes_excluded(
        self, db_session: Session, test_household: Household, other_household: Household,
    ) -> None:
        _seed_dish(db_session, "biryani", other_household.id)
        db_session.commit()

        results = search_dishes(db_session, "biryani", household_id=test_household.id)
        assert len(results) == 0

    def test_pagination_limit(
        self, db_session: Session, test_household: Household,
    ) -> None:
        for i in range(5):
            _seed_dish(db_session, f"dish {i}", test_household.id)
        db_session.commit()

        results = search_dishes(
            db_session, "dish", household_id=test_household.id, limit=2,
        )
        assert len(results) == 2

    def test_pagination_offset(
        self, db_session: Session, test_household: Household,
    ) -> None:
        for i in range(5):
            _seed_dish(db_session, f"dish {i}", test_household.id)
        db_session.commit()

        all_results = search_dishes(
            db_session, "dish", household_id=test_household.id, limit=10,
        )
        offset_results = search_dishes(
            db_session, "dish", household_id=test_household.id, limit=10, offset=2,
        )
        assert len(offset_results) == len(all_results) - 2


# ---------------------------------------------------------------------------
# find_or_create_dish
# ---------------------------------------------------------------------------


class TestFindOrCreateDish:
    """Verify exact-match → fuzzy-match → create pipeline."""

    def test_exact_match_returns_existing(
        self, db_session: Session, test_household: Household,
    ) -> None:
        existing = _seed_dish(db_session, "rajma chawal", test_household.id)
        db_session.commit()

        result = find_or_create_dish(
            db_session, "Rajma Chawal", household_id=test_household.id,
        )
        assert result.id == existing.id

    def test_fuzzy_match_corrects_typo(
        self, db_session: Session, test_household: Household,
    ) -> None:
        existing = _seed_dish(db_session, "palak paneer", test_household.id)
        db_session.commit()

        result = find_or_create_dish(
            db_session, "palak paner", household_id=test_household.id,
        )
        assert result.id == existing.id

    def test_no_match_creates_new(
        self, db_session: Session, test_household: Household,
    ) -> None:
        result = find_or_create_dish(
            db_session, "unique new dish", household_id=test_household.id,
        )
        db_session.commit()

        assert result.name == "unique new dish"
        fetched = db_session.get(Dish, result.id)
        assert fetched is not None

    def test_household_dish_shadows_global(
        self, db_session: Session, test_household: Household,
    ) -> None:
        global_dish = _seed_dish(db_session, "dal fry", household_id=None)
        hh_dish = _seed_dish(db_session, "dal fry", test_household.id)
        db_session.commit()

        result = find_or_create_dish(
            db_session, "dal fry", household_id=test_household.id,
        )
        assert result.id == hh_dish.id

    @patch("app.services.dish.get_current_meal_type", return_value="dinner")
    def test_defaults_meal_type_from_time(
        self, mock_meal, db_session: Session, test_household: Household,
    ) -> None:
        result = find_or_create_dish(
            db_session, "brand new dish", household_id=test_household.id,
        )
        db_session.commit()
        assert result.meal_type == "dinner"

    def test_explicit_meal_type_used(
        self, db_session: Session, test_household: Household,
    ) -> None:
        result = find_or_create_dish(
            db_session,
            "breakfast item",
            household_id=test_household.id,
            meal_type="breakfast",
        )
        db_session.commit()
        assert result.meal_type == "breakfast"

    def test_optional_fields_applied(
        self, db_session: Session, test_household: Household,
    ) -> None:
        result = find_or_create_dish(
            db_session,
            "spicy thing",
            household_id=test_household.id,
            dish_type="non-veg",
            spiciness=4,
            prep_time_minutes=45,
            calories_estimate=500,
        )
        db_session.commit()
        assert result.dish_type == "non-veg"
        assert result.spiciness == 4
        assert result.prep_time_minutes == 45
        assert result.calories_estimate == 500


# ---------------------------------------------------------------------------
# create_cook_log
# ---------------------------------------------------------------------------


class TestCreateCookLog:
    """Verify cook log persistence."""

    def test_creates_log_with_all_fields(
        self, db_session: Session, test_user: User, test_household: Household,
    ) -> None:
        dish = _seed_dish(db_session, "test dish", test_household.id)
        db_session.commit()

        log = create_cook_log(
            db_session,
            household_id=test_household.id,
            user_id=test_user.id,
            dish_id=dish.id,
            note="delicious",
            rating=5,
        )
        db_session.commit()

        assert log.user_id == test_user.id
        assert log.dish_id == dish.id
        assert log.note == "delicious"
        assert log.rating == 5

    def test_optional_fields_nullable(
        self, db_session: Session, test_user: User, test_household: Household,
    ) -> None:
        dish = _seed_dish(db_session, "basic dish", test_household.id)
        db_session.commit()

        log = create_cook_log(
            db_session,
            household_id=test_household.id,
            user_id=test_user.id,
            dish_id=dish.id,
        )
        db_session.commit()

        assert log.note is None
        assert log.rating is None

    def test_flush_without_commit(
        self, db_session: Session, test_user: User, test_household: Household,
    ) -> None:
        """create_cook_log only flushes — caller is responsible for commit."""
        dish = _seed_dish(db_session, "flush test", test_household.id)
        db_session.commit()

        log = create_cook_log(
            db_session,
            household_id=test_household.id,
            user_id=test_user.id,
            dish_id=dish.id,
        )
        # Log has an ID (flushed) even without commit
        assert log.id is not None


# ---------------------------------------------------------------------------
# _attach_ingredients_to_dish
# ---------------------------------------------------------------------------


class TestAttachIngredients:
    """Verify ingredient creation and attachment logic."""

    def test_creates_new_ingredients(
        self, db_session: Session, test_household: Household,
    ) -> None:
        dish = _seed_dish(db_session, "test dish", test_household.id)
        db_session.commit()

        _attach_ingredients_to_dish(db_session, dish, ["Spinach", "Paneer"])
        db_session.commit()

        names = {ing.name for ing in dish.ingredients}
        assert names == {"spinach", "paneer"}

    def test_reuses_existing_ingredients(
        self, db_session: Session, test_household: Household,
    ) -> None:
        existing = Ingredient(name="garlic")
        db_session.add(existing)
        dish = _seed_dish(db_session, "garlic dish", test_household.id)
        db_session.commit()

        _attach_ingredients_to_dish(db_session, dish, ["Garlic"])
        db_session.commit()

        assert len(dish.ingredients) == 1
        assert dish.ingredients[0].id == existing.id

    def test_no_duplicates_on_repeated_call(
        self, db_session: Session, test_household: Household,
    ) -> None:
        dish = _seed_dish(db_session, "dup dish", test_household.id)
        db_session.commit()

        _attach_ingredients_to_dish(db_session, dish, ["tomato"])
        db_session.commit()
        _attach_ingredients_to_dish(db_session, dish, ["tomato"])
        db_session.commit()

        assert len(dish.ingredients) == 1

    def test_empty_list_is_noop(
        self, db_session: Session, test_household: Household,
    ) -> None:
        dish = _seed_dish(db_session, "empty dish", test_household.id)
        db_session.commit()

        _attach_ingredients_to_dish(db_session, dish, [])
        db_session.commit()

        assert dish.ingredients == []


# ---------------------------------------------------------------------------
# enrich_dish_background_task
# ---------------------------------------------------------------------------


class TestEnrichDishBackgroundTask:
    """Verify background enrichment task behaviour."""

    def test_skips_nonexistent_dish(self) -> None:
        import uuid
        with patch("app.services.dish.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            mock_session_cls.return_value = mock_db
            mock_db.get.return_value = None
            _enrich_dish_sync(uuid.uuid4())
            mock_db.commit.assert_not_called()

    def test_skips_fully_enriched_dish(
        self, db_session: Session, test_household: Household,
    ) -> None:
        dish = _seed_dish(db_session, "full dish", test_household.id)
        ing = Ingredient(name="onion")
        db_session.add(ing)
        db_session.flush()
        dish.ingredients.append(ing)
        dish.calories_estimate = 300
        dish.prep_time_minutes = 20
        db_session.commit()

        with patch("app.services.dish.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            mock_session_cls.return_value = mock_db
            mock_db.get.return_value = dish
            with patch("app.services.dish.enrich_dish_with_gemini") as mock_llm:
                _enrich_dish_sync(dish.id)
                mock_llm.assert_not_called()

    def test_enriches_dish_when_data_missing(
        self, db_session: Session, test_household: Household,
    ) -> None:
        dish = _seed_dish(db_session, "bare dish", test_household.id)
        db_session.commit()

        from app.services.llm import DishEnrichmentResult

        mock_result = DishEnrichmentResult(
            ingredients=["potato", "oil"],
            prep_time_minutes=15,
            calories_estimate=200,
        )

        with patch("app.services.dish.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            mock_session_cls.return_value = mock_db
            mock_db.get.return_value = dish
            with patch("app.services.dish.enrich_dish_with_gemini", return_value=mock_result):
                with patch("app.services.dish._attach_ingredients_to_dish") as mock_attach:
                    _enrich_dish_sync(dish.id)
                    mock_attach.assert_called_once()
                    assert dish.calories_estimate == 200
                    assert dish.prep_time_minutes == 15
                    mock_db.commit.assert_called_once()

    def test_rolls_back_on_exception(self) -> None:
        import uuid
        with patch("app.services.dish.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            mock_session_cls.return_value = mock_db
            mock_db.get.side_effect = Exception("db error")
            _enrich_dish_sync(uuid.uuid4())
            mock_db.rollback.assert_called_once()
            mock_db.close.assert_called_once()
