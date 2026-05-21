"""Asynchronous dish search & creation HTTP endpoints for V2 API."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_async_db
from app.models.users import User
from app.schemas.dishes import DishCreate, DishRead, DishSearchResponse
from app.services.cooklogs_async import create_cook_log_async
from app.services.dish import (
    enrich_dish_background_task_async,
    find_or_create_dish_async,
    search_dishes_async,
)
from app.utils.auth import get_current_user_async
from app.utils.rate_limit import limiter

router = APIRouter(prefix="/dishes", tags=["dishes"])
logger = logging.getLogger(__name__)


@router.get("/search", response_model=list[DishSearchResponse])
@limiter.limit("20/minute")
async def search_dishes_endpoint(
    request: Request,
    q: str,
    user: User = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
    limit: int = Query(default=5, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    """Search for dishes by name using fuzzy matching asynchronously."""
    q = q.lower().strip()
    if len(q) < 3:
        return []

    return await search_dishes_async(
        db, q, household_id=user.household_id, limit=limit, offset=offset
    )


@router.post("/", response_model=DishRead)
@limiter.limit("10/minute")
async def create_dish(
    request: Request,
    dish_data: DishCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
):
    """Log a cooked dish asynchronously."""
    logger.info("Dish log request user_id=%s input=%s asynchronously", user.id, dish_data.name)

    dish = await find_or_create_dish_async(
        db,
        dish_data.name,
        household_id=user.household_id,
        dish_type=dish_data.dish_type,
        meal_type=dish_data.meal_type,
        spiciness=dish_data.spiciness,
        prep_time_minutes=dish_data.prep_time_minutes,
        calories_estimate=dish_data.calories_estimate,
        ingredients=dish_data.ingredients,
    )

    await create_cook_log_async(
        db,
        household_id=user.household_id,
        user_id=user.id,
        dish_id=dish.id,
        note=dish_data.note,
        rating=dish_data.rating,
    )

    await db.commit()
    await db.refresh(dish, ["ingredients"])

    if not (dish.ingredients and dish.calories_estimate and dish.prep_time_minutes):
        background_tasks.add_task(enrich_dish_background_task_async, dish.id)

    logger.info(
        "Recorded cook event asynchronously for dish_id=%s rating=%s",
        dish.id,
        dish_data.rating,
    )
    return dish
