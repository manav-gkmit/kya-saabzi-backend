import difflib
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.helpers import escape_like
from app.models.dishes import Dish
from app.services.dish.ingredients import attach_ingredients_to_dish_async
from app.utils.time import get_current_meal_type

logger = logging.getLogger(__name__)


async def get_exact_dish_async(db: AsyncSession, input_name: str, household_id: UUID) -> Dish | None:
    stmt = (
        select(Dish)
        .where(
            func.lower(Dish.name) == input_name,
            (Dish.household_id == household_id) | (Dish.household_id.is_(None)),
        )
        .order_by(Dish.household_id.is_(None))
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_fuzzy_dish_async(db: AsyncSession, input_name: str, household_id: UUID) -> Dish | None:
    first_word = (
        escape_like(input_name.split()[0]) if input_name.strip() else escape_like(input_name)
    )
    stmt = (
        select(Dish.id, Dish.name, Dish.household_id)
        .where(
            Dish.name.ilike(f"%{first_word}%", escape="\\"),
            (Dish.household_id == household_id) | (Dish.household_id.is_(None)),
        )
        .order_by(Dish.household_id.is_(None), Dish.name)
        .limit(10)
    )
    result = await db.execute(stmt)
    candidates = result.all()

    name_map: dict[str, Any] = {}
    for d in candidates:
        key = d.name.lower()
        if key not in name_map or (
            name_map[key].household_id is None and d.household_id is not None
        ):
            name_map[key] = d

    if not name_map:
        return None

    close = difflib.get_close_matches(
        input_name,
        list(name_map.keys()),
        n=1,
        cutoff=0.85,
    )
    if close:
        matched = name_map[close[0]]
        dish = await db.get(Dish, matched.id)
        if dish:
            logger.info(
                "Automatic typo correction: '%s' → '%s' (ID: %s)",
                input_name,
                matched.name,
                matched.id,
            )
            return dish
    return None


async def create_dish_record_async(
    db: AsyncSession,
    input_name: str,
    household_id: UUID,
    dish_type: str | None = None,
    meal_type: str | None = None,
    spiciness: int | None = None,
    prep_time_minutes: int | None = None,
    calories_estimate: int | None = None,
) -> Dish:
    resolved_meal = meal_type or get_current_meal_type()
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
    await db.flush()
    logger.info("Created new canonical dish: %s", input_name)
    return dish


async def find_or_create_dish_async(
    db: AsyncSession,
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
    input_name = name.lower().strip()
    if not input_name:
        raise ValueError("Dish name cannot be empty after normalization")

    dish = await get_exact_dish_async(db, input_name, household_id)
    if dish:
        logger.debug("Using existing dish: %s", dish.name)
        if ingredients:
            await attach_ingredients_to_dish_async(db, dish, ingredients)
            await db.flush()
        return dish

    dish = await get_fuzzy_dish_async(db, input_name, household_id)
    if dish:
        if ingredients:
            await attach_ingredients_to_dish_async(db, dish, ingredients)
            await db.flush()
        return dish

    dish = await create_dish_record_async(
        db,
        input_name,
        household_id,
        dish_type,
        meal_type,
        spiciness,
        prep_time_minutes,
        calories_estimate,
    )

    if ingredients:
        await attach_ingredients_to_dish_async(db, dish, ingredients)
        await db.flush()

    return dish
