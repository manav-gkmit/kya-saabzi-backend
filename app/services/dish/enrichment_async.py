import asyncio
import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import AsyncSessionLocal
from app.models.dishes import Dish
from app.services.dish.ingredients import attach_ingredients_to_dish_async
from app.services.llm import enrich_dish_with_gemini_async

logger = logging.getLogger(__name__)

_ENRICHMENT_IN_PROGRESS: set[str] = set()
_ENRICHMENT_LOCK = asyncio.Lock()


async def _copy_metadata_if_exists_async(
    db: AsyncSession, dish: Dish, dish_name_lower: str
) -> bool:
    """Returns True if it found and copied metadata from an existing dish asynchronously."""
    stmt = select(Dish).where(
        func.lower(Dish.name) == dish_name_lower,
        Dish.id != dish.id,
        Dish.calories_estimate.isnot(None),
        Dish.prep_time_minutes.isnot(None),
    )
    result = await db.execute(stmt)
    existing_enriched = result.scalars().first()

    if existing_enriched:
        logger.info("Found existing enriched dish for '%s', copying metadata", dish.name)
        await db.refresh(existing_enriched, ["ingredients"])
        if existing_enriched.ingredients and not dish.ingredients:
            await attach_ingredients_to_dish_async(
                db, dish, [ing.name for ing in existing_enriched.ingredients]
            )
        if dish.calories_estimate is None:
            dish.calories_estimate = existing_enriched.calories_estimate
        if dish.prep_time_minutes is None:
            dish.prep_time_minutes = existing_enriched.prep_time_minutes
        await db.commit()
        return True
    return False


async def _apply_gemini_result_async(
    db: AsyncSession, dish_name: str, dish_name_lower: str, result
) -> None:
    """Applies Gemini result to all dishes with the same name missing metadata asynchronously."""
    if not result:
        return

    stmt = select(Dish).where(func.lower(Dish.name) == dish_name_lower)
    db_result = await db.execute(stmt)
    dishes_to_update = db_result.scalars().all()
    for d in dishes_to_update:
        if not d.ingredients and result.ingredients:
            await attach_ingredients_to_dish_async(db, d, result.ingredients)
        if d.calories_estimate is None and result.calories_estimate is not None:
            d.calories_estimate = result.calories_estimate
        if d.prep_time_minutes is None and result.prep_time_minutes is not None:
            d.prep_time_minutes = result.prep_time_minutes

    await db.commit()
    logger.info("Successfully enriched dishes with name: %s", dish_name)


async def enrich_dish_background_task_async(dish_id: UUID) -> None:
    """Background task wrapper — fully async non-blocking enrichment."""
    async with AsyncSessionLocal() as db:
        try:
            dish = await db.get(Dish, dish_id)
            if not dish:
                return

            await db.refresh(dish, ["ingredients"])

            if (
                dish.ingredients
                and dish.calories_estimate is not None
                and dish.prep_time_minutes is not None
            ):
                return

            dish_name_lower = dish.name.lower()

            if await _copy_metadata_if_exists_async(db, dish, dish_name_lower):
                return

            async with _ENRICHMENT_LOCK:
                if dish_name_lower in _ENRICHMENT_IN_PROGRESS:
                    logger.info(
                        "Enrichment already in progress for '%s', skipping API call",
                        dish.name,
                    )
                    return
                _ENRICHMENT_IN_PROGRESS.add(dish_name_lower)

            try:
                logger.info("Triggering Gemini enrichment for dish: %s", dish.name)
                result = await enrich_dish_with_gemini_async(dish.name)
                await _apply_gemini_result_async(db, dish.name, dish_name_lower, result)
            finally:
                async with _ENRICHMENT_LOCK:
                    _ENRICHMENT_IN_PROGRESS.discard(dish_name_lower)

        except Exception:
            logger.exception("Error in enrich_dish_background_task_async")
            await db.rollback()
