"""Dish search & creation HTTP endpoints — thin adapter over services."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.models.users import User
from app.schemas.dishes import DishCreate, DishRead, DishSearchResponse
from app.services.dish import create_cook_log, find_or_create_dish, search_dishes, enrich_dish_background_task
from app.utils.auth import get_current_user

router = APIRouter(prefix="/dishes", tags=["dishes"])
logger = logging.getLogger(__name__)


@router.get("/search", response_model=list[DishSearchResponse])
def search_dishes_endpoint(
    q: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=5, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    """Search for dishes by name using fuzzy matching."""
    q = q.lower().strip()
    if len(q) < 3:
        return []

    return search_dishes(db, q, household_id=user.household_id, limit=limit, offset=offset)


@router.post("/", response_model=DishRead)
def create_dish(
    dish_data: DishCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log a cooked dish — finds or creates the canonical entry, then records the cook event."""
    logger.info("Dish log request user_id=%s input=%s", user.id, dish_data.name)

    dish = find_or_create_dish(
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

    create_cook_log(
        db,
        household_id=user.household_id,
        user_id=user.id,
        dish_id=dish.id,
        note=dish_data.note,
        rating=dish_data.rating,
    )

    db.commit()
    db.refresh(dish)

    if not (dish_data.ingredients and dish_data.calories_estimate and dish_data.prep_time_minutes):
        background_tasks.add_task(enrich_dish_background_task, dish.id)

    logger.info(
        "Recorded cook event for dish_id=%s rating=%s",
        dish.id,
        dish_data.rating,
    )
    return dish
