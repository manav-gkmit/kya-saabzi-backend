"""Dish lookup, creation, and fuzzy-search business logic."""

from __future__ import annotations

import asyncio
import difflib
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.database.helpers import escape_like
from app.models.cooklogs import CookLog
from app.models.dishes import Dish, Ingredient
from app.services.llm import enrich_dish_with_gemini
from app.utils.time import get_current_meal_type

logger = logging.getLogger(__name__)

DEFAULT_FALLBACK_LIMIT = 50

# Upper bound on candidate rows fetched from DB before Python-level similarity scoring.
# Keeps memory usage O(1) regardless of table size.
_SEARCH_CANDIDATE_LIMIT = 100


def search_dishes(
    db: Session,
    query: str,
    *,
    household_id: UUID,
    limit: int = 5,
    offset: int = 0,
) -> list[dict]:
    """Return dishes matching *query*, scored and sorted by similarity.

    Args:
        db: Active database session.
        query: Normalised (lower, stripped) search term.
        limit: Maximum results to return.
        offset: Offset for pagination.

    Returns:
        List of ``{"id", "name", "similarity"}`` dicts, sorted by similarity
        descending.

    Note:
        At most ``_SEARCH_CANDIDATE_LIMIT`` rows are fetched from the database
        before Python-level scoring.  ``offset`` and ``limit`` are applied to
        the scored slice, so requesting an ``offset`` ≥ ``_SEARCH_CANDIDATE_LIMIT``
        will return an empty list even if the ILIKE filter matches more records.
    """
    q_escaped = escape_like(query)
    # Fetch a bounded candidate set from the database using ILIKE pre-filtering.
    rows = (
        db.query(Dish.id, Dish.name)
        .filter(Dish.name.ilike(f"%{q_escaped}%", escape="\\"))
        .filter((Dish.household_id == household_id) | (Dish.household_id.is_(None)))
        .limit(_SEARCH_CANDIDATE_LIMIT)
        .all()
    )

    # Compute real similarity scores in Python against the bounded candidate set.
    q_lower = query.lower()
    scored: list[dict] = [
        {
            "id": dish_id,
            "name": dish_name,
            "similarity": difflib.SequenceMatcher(None, q_lower, dish_name.lower()).ratio(),
        }
        for dish_id, dish_name in rows
    ]

    # Sort by similarity descending, then apply pagination.
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[offset : offset + limit]


def find_or_create_dish(
    db: Session,
    name: str,
    *,
    household_id: UUID,
    dish_type: str | None = None,
    meal_type: str | None = None,
    spiciness: int | None = None,
    prep_time_minutes: int | None = None,
    calories_estimate: int | None = None,
    ingredients: list[str] | None = None,
) -> Dish:
    """Exact-match → fuzzy-match → create-new pipeline for a dish.

    Uses a single transaction so the dish and any follow-up cooklog
    can be committed atomically by the caller.
    """
    input_name = name.lower().strip()

    dish = (
        db.query(Dish)
        .filter(
            func.lower(Dish.name) == input_name,
            (Dish.household_id == household_id) | (Dish.household_id.is_(None)),
        )
        .order_by(Dish.household_id.is_(None))
        .first()
    )
    if dish:
        logger.debug("Using existing dish: %s", dish.name)
        if ingredients:
            _attach_ingredients_to_dish(db, dish, ingredients)
            db.flush()
        return dish

    # Targeted fuzzy matching: use the first word for a broader ILIKE filter,
    # then let difflib score the full name for precision.
    first_word = (
        escape_like(input_name.split()[0]) if input_name.strip() else escape_like(input_name)
    )
    candidates = (
        db.query(Dish.id, Dish.name, Dish.household_id)
        .filter(
            Dish.name.ilike(f"%{first_word}%", escape="\\"),
            (Dish.household_id == household_id) | (Dish.household_id.is_(None)),
        )
        .order_by(Dish.household_id.is_(None), Dish.name)
        .limit(10)
        .all()
    )

    name_map: dict[str, Any] = {}
    for d in candidates:
        key = d.name.lower()
        if key not in name_map or (
            name_map[key].household_id is None and d.household_id is not None
        ):
            name_map[key] = d

    if name_map:
        close = difflib.get_close_matches(
            input_name,
            list(name_map.keys()),
            n=1,
            cutoff=0.85,
        )
        if close:
            matched = name_map[close[0]]
            dish = db.get(Dish, matched.id)
            if dish:
                logger.info(
                    "Automatic typo correction: '%s' → '%s' (ID: %s)",
                    input_name,
                    matched.name,
                    matched.id,
                )
                if ingredients:
                    _attach_ingredients_to_dish(db, dish, ingredients)
                    db.flush()
                return dish

    resolved_meal = meal_type or get_current_meal_type()

    # Avoid passing None for columns with nullable=False to use DB defaults
    dish_kwargs = {
        "name": input_name,
        "household_id": household_id,
        "meal_type": resolved_meal,
    }
    if dish_type is not None:
        dish_kwargs["dish_type"] = dish_type
    if spiciness is not None:
        dish_kwargs["spiciness"] = spiciness
    if prep_time_minutes is not None:
        dish_kwargs["prep_time_minutes"] = prep_time_minutes
    if calories_estimate is not None:
        dish_kwargs["calories_estimate"] = calories_estimate

    dish = Dish(**dish_kwargs)
    db.add(dish)
    db.flush()
    logger.info("Created new canonical dish: %s", input_name)

    if ingredients:
        _attach_ingredients_to_dish(db, dish, ingredients)
        db.flush()

    return dish


def _attach_ingredients_to_dish(db: Session, dish: Dish, ingredient_names: list[str]) -> None:
    """Find or create ingredients by name and attach them to the given dish."""
    normalized_names = {name.lower().strip() for name in ingredient_names if name.strip()}
    if not normalized_names:
        return

    # Find existing ingredients
    existing_ingredients = (
        db.query(Ingredient).filter(func.lower(Ingredient.name).in_(normalized_names)).all()
    )

    existing_map = {ing.name.lower(): ing for ing in existing_ingredients}

    # Identify which ones need to be created
    to_create = normalized_names - set(existing_map.keys())

    new_ingredients = []
    for name in to_create:
        ing = Ingredient(name=name)
        new_ingredients.append(ing)
        db.add(ing)

    if new_ingredients:
        db.flush()
        for ing in new_ingredients:
            existing_map[ing.name.lower()] = ing

    # Identify currently linked ingredients to avoid duplication
    current_ingredient_names = {ing.name.lower() for ing in dish.ingredients}

    for name in normalized_names:
        if name not in current_ingredient_names:
            dish.ingredients.append(existing_map[name])


def create_cook_log(
    db: Session,
    *,
    household_id: UUID,
    user_id: UUID,
    dish_id: UUID,
    note: str | None = None,
    rating: int | None = None,
) -> CookLog:
    """Persist a new cook event."""
    log = CookLog(
        household_id=household_id,
        user_id=user_id,
        dish_id=dish_id,
        note=note,
        rating=rating,
    )
    db.add(log)
    db.flush()
    return log


def _enrich_dish_sync(dish_id: UUID) -> None:
    """Synchronous enrichment logic — intended to run off the main thread."""
    db = SessionLocal()
    try:
        dish = db.get(Dish, dish_id)
        if not dish:
            return

        if (
            dish.ingredients
            and dish.calories_estimate is not None
            and dish.prep_time_minutes is not None
        ):
            return

        logger.info("Triggering Gemini enrichment for dish: %s", dish.name)
        result = enrich_dish_with_gemini(dish.name)
        if not result:
            return

        if not dish.ingredients and result.ingredients:
            _attach_ingredients_to_dish(db, dish, result.ingredients)

        if dish.calories_estimate is None and result.calories_estimate is not None:
            dish.calories_estimate = result.calories_estimate

        if dish.prep_time_minutes is None and result.prep_time_minutes is not None:
            dish.prep_time_minutes = result.prep_time_minutes

        db.commit()
        logger.info("Successfully enriched dish: %s", dish.name)
    except Exception as e:
        logger.error("Error in enrich_dish_background_task: %s", e)
        db.rollback()
    finally:
        db.close()


async def enrich_dish_background_task(dish_id: UUID) -> None:
    """Background task wrapper — offloads blocking Gemini I/O to a thread."""
    await asyncio.to_thread(_enrich_dish_sync, dish_id)
