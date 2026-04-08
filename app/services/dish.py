"""Dish lookup, creation, and fuzzy-search business logic."""
from __future__ import annotations

import difflib
import logging

from sqlalchemy.orm import Session

from app.database.helpers import escape_like
from app.models.cooklogs import CookLog
from app.models.dishes import Dish
from app.utils.time import get_current_meal_type

logger = logging.getLogger(__name__)


def search_dishes(
    db: Session,
    query: str,
    *,
    limit: int = 5,
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
        .all()
    )

    if not candidates:
        candidates = db.query(Dish.id, Dish.name).all()

    results: list[dict] = []
    for dish_id, dish_name in candidates:
        similarity = difflib.SequenceMatcher(None, query, dish_name).ratio()
        if similarity > 0.4:
            results.append({
                "id": dish_id,
                "name": dish_name,
                "similarity": similarity,
            })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]


def find_or_create_dish(
    db: Session,
    name: str,
    *,
    dish_type: str | None = None,
    meal_type: str | None = None,
    spiciness: int | None = None,
    prep_time_minutes: int | None = None,
    calories_estimate: int | None = None,
) -> Dish:
    """Exact-match → fuzzy-match → create-new pipeline for a dish.

    Uses a single transaction so the dish and any follow-up cooklog
    can be committed atomically by the caller.
    """
    input_name = name.lower().strip()

    dish = db.query(Dish).filter(Dish.name == input_name).first()
    if dish:
        logger.debug("Using existing dish: %s", dish.name)
        return dish

    existing = db.query(Dish.id, Dish.name).all()
    close = difflib.get_close_matches(
        input_name,
        [d.name for d in existing],
        n=1,
        cutoff=0.85,
    )
    if close:
        matched = next(d for d in existing if d.name == close[0])
        dish = db.get(Dish, matched.id)
        logger.info(
            "Automatic typo correction: '%s' → '%s'",
            input_name,
            close[0],
        )
        return dish  # type: ignore[return-value]

    resolved_meal = meal_type or get_current_meal_type()
    dish = Dish(
        name=input_name,
        dish_type=dish_type,
        meal_type=resolved_meal,
        spiciness=spiciness,
        prep_time_minutes=prep_time_minutes,
        calories_estimate=calories_estimate,
    )
    db.add(dish)
    db.flush()
    logger.info("Created new canonical dish: %s", input_name)
    return dish


def create_cook_log(
    db: Session,
    *,
    household_id: object,
    user_id: object,
    dish_id: object,
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
