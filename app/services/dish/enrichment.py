import asyncio
import logging
import threading
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.models.dishes import Dish
from app.services.dish.ingredients import attach_ingredients_to_dish
from app.services.llm import enrich_dish_with_gemini

logger = logging.getLogger(__name__)

_ENRICHMENT_IN_PROGRESS: set[str] = set()
_ENRICHMENT_LOCK = threading.Lock()


def _copy_metadata_if_exists(db: Session, dish: Dish, dish_name_lower: str) -> bool:
    """Returns True if it found and copied metadata from an existing dish."""
    existing_enriched = (
        db.query(Dish)
        .filter(
            func.lower(Dish.name) == dish_name_lower,
            Dish.id != dish.id,
            Dish.calories_estimate.isnot(None),
            Dish.prep_time_minutes.isnot(None),
        )
        .first()
    )

    if existing_enriched and existing_enriched.ingredients:
        logger.info("Found existing enriched dish for '%s', copying metadata", dish.name)
        if not dish.ingredients:
            attach_ingredients_to_dish(
                db, dish, [ing.name for ing in existing_enriched.ingredients]
            )
        if dish.calories_estimate is None:
            dish.calories_estimate = existing_enriched.calories_estimate
        if dish.prep_time_minutes is None:
            dish.prep_time_minutes = existing_enriched.prep_time_minutes
        db.commit()
        return True
    return False


def _apply_gemini_result(db: Session, dish_name: str, dish_name_lower: str, result) -> None:
    """Applies Gemini result to all dishes with the same name missing metadata."""
    if not result:
        return

    dishes_to_update = db.query(Dish).filter(func.lower(Dish.name) == dish_name_lower).all()
    for d in dishes_to_update:
        if not d.ingredients and result.ingredients:
            attach_ingredients_to_dish(db, d, result.ingredients)
        if d.calories_estimate is None and result.calories_estimate is not None:
            d.calories_estimate = result.calories_estimate
        if d.prep_time_minutes is None and result.prep_time_minutes is not None:
            d.prep_time_minutes = result.prep_time_minutes

    db.commit()
    logger.info("Successfully enriched dishes with name: %s", dish_name)


def _enrich_dish_sync(dish_id: UUID) -> None:
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

        dish_name_lower = dish.name.lower()

        if _copy_metadata_if_exists(db, dish, dish_name_lower):
            return

        with _ENRICHMENT_LOCK:
            if dish_name_lower in _ENRICHMENT_IN_PROGRESS:
                logger.info("Enrichment already in progress for '%s', skipping API call", dish.name)
                return
            _ENRICHMENT_IN_PROGRESS.add(dish_name_lower)

        try:
            logger.info("Triggering Gemini enrichment for dish: %s", dish.name)
            result = enrich_dish_with_gemini(dish.name)
            _apply_gemini_result(db, dish.name, dish_name_lower, result)
        finally:
            with _ENRICHMENT_LOCK:
                _ENRICHMENT_IN_PROGRESS.discard(dish_name_lower)

    except Exception as e:
        logger.error("Error in enrich_dish_background_task: %s", e)
        db.rollback()
    finally:
        db.close()


async def enrich_dish_background_task(dish_id: UUID) -> None:
    """Background task wrapper — offloads blocking Gemini I/O to a thread."""
    await asyncio.to_thread(_enrich_dish_sync, dish_id)
