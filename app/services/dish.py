"""Dish lookup, creation, and fuzzy-search business logic."""
from __future__ import annotations

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


def search_dishes(
    db: Session,
    query: str,
    *,
    household_id: UUID,
    limit: int = 5,
    offset: int = 0,
) -> list[dict]:
    """Return dishes matching *query* using ILIKE + difflib fallback.

    Args:
        db: Active database session.
        query: Normalised (lower, stripped) search term.
        limit: Maximum results to return.

    Returns:
        Sorted list of ``{"id", "name", "similarity"}`` dicts.
    """
    q_escaped = escape_like(query)
    candidates = (
        db.query(Dish.id, Dish.name)
        .filter(Dish.name.ilike(f"%{q_escaped}%", escape="\\"))
        .filter((Dish.household_id == household_id) | (Dish.household_id.is_(None)))
        .all()
    )

    if not candidates:
        candidates = (
            db.query(Dish.id, Dish.name)
            .filter((Dish.household_id == household_id) | (Dish.household_id.is_(None)))
            .limit(DEFAULT_FALLBACK_LIMIT)
            .all()
        )

    results: list[dict] = []
    for dish_id, dish_name in candidates:
        # Compute similarity from normalized values to ignore case differences
        similarity = difflib.SequenceMatcher(None, query, dish_name.lower()).ratio()
        if similarity > 0.4:
            results.append({
                "id": dish_id,
                "name": dish_name,
                "similarity": similarity,
            })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    results = results[offset:]
    return results[:limit]


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

    dish = db.query(Dish).filter(
        func.lower(Dish.name) == input_name,
        (Dish.household_id == household_id) | (Dish.household_id.is_(None))
    ).order_by(Dish.household_id.is_(None)).first()
    if dish:
        logger.debug("Using existing dish: %s", dish.name)
        if ingredients:
            _attach_ingredients_to_dish(db, dish, ingredients)
            db.flush()
        return dish

    existing = db.query(Dish.id, Dish.name, Dish.household_id).filter(
        (Dish.household_id == household_id) | (Dish.household_id.is_(None))
    ).all()
    # Normalize candidate names for fuzzy matching; household-specific rows
    # shadow global ones so a household override is always preferred.
    name_map: dict[str, Any] = {}
    for d in existing:
        key = d.name.lower()
        if key not in name_map or (
            name_map[key].household_id is None and d.household_id is not None
        ):
            name_map[key] = d
    close = difflib.get_close_matches(
        input_name,
        list(name_map.keys()),
        n=1,
        cutoff=0.85,
    )
    if close:
        matched = name_map[close[0]]
        dish = db.get(Dish, matched.id)
        logger.info(
            "Automatic typo correction: '%s' → '%s' (ID: %s)",
            input_name,
            matched.name,
            matched.id,
        )
        if ingredients and dish:
            _attach_ingredients_to_dish(db, dish, ingredients)
            db.flush()
        return dish  # type: ignore[return-value]

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
    existing_ingredients = db.query(Ingredient).filter(
        func.lower(Ingredient.name).in_(normalized_names)
    ).all()
    
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

def enrich_dish_background_task(dish_id: UUID) -> None:
    """Background task to fetch missing dish data from Gemini."""
    db = SessionLocal()
    try:
        dish = db.get(Dish, dish_id)
        if not dish:
            return

        if dish.ingredients is not None and dish.calories_estimate is not None and dish.prep_time_minutes is not None:
            return

        logger.info(f"Triggering Gemini enrichment for dish: {dish.name}")
        result = enrich_dish_with_gemini(dish.name)
        if not result:
            return

        if dish.ingredients is None and result.ingredients:
            _attach_ingredients_to_dish(db, dish, result.ingredients)
            
        if dish.calories_estimate is None and result.calories_estimate is not None:
            dish.calories_estimate = result.calories_estimate
            
        if dish.prep_time_minutes is None and result.prep_time_minutes is not None:
            dish.prep_time_minutes = result.prep_time_minutes

        db.commit()
        logger.info(f"Successfully enriched dish: {dish.name}")
    except Exception as e:
        logger.error(f"Error in enrich_dish_background_task: {e}")
        db.rollback()
    finally:
        db.close()
