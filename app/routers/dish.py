import logging
import difflib
from typing import List, Optional

from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.orm import Session

from app.util import get_current_user, get_current_meal_type
from app.database.db import get_db
from app.schemas.dishes import DishCreate, DishRead, DishSearchResponse
from app.models.users import User
from app.models.dishes import Dish
from app.models.cooklogs import CookLog


router = APIRouter(prefix="/dishes", tags=["dishes"])
logger = logging.getLogger(__name__)


@router.get("/search", response_model=List[DishSearchResponse])
async def search_dishes(
    q: str,
    db: Session = Depends(get_db),
    limit: int = Query(default=5, ge=1, le=50),
):
    """
    Search for dishes by name using fuzzy matching.
    Helps prevent duplicate entries (e.g. 'palak paneer' vs 'palakpaner').
    """
    q = q.lower().strip()
    # Escape SQL LIKE wildcards in user input to avoid unintended pattern expansion.
    q_escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    # Prefilter at DB level: only load dishes whose name contains the query string.
    # This avoids loading the entire table into memory for the common case.
    candidates = (
        db.query(Dish.id, Dish.name)
        .filter(Dish.name.ilike(f"%{q_escaped}%", escape="\\"))
        .all()
    )
    # If no DB-level candidates are found, fall back to all dishes so that
    # difflib can still catch near-miss typos (e.g. 'palakpaner').
    if not candidates:
        candidates = db.query(Dish.id, Dish.name).all()
    
    results = []
    for dish_id, dish_name in candidates:
        similarity = difflib.SequenceMatcher(None, q, dish_name).ratio()
        if similarity > 0.4: # Lower threshold for search, results will be sorted
            results.append({
                "id": dish_id,
                "name": dish_name,
                "similarity": similarity
            })
    
    # Sort by similarity and return top results
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]


@router.post("/", response_model=DishRead)
async def create_dish(
    dish_data: DishCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Smarter dish logging:
    1. Checks for exact name match.
    2. Checks for near-matches (typo handling) to prevent duplicate entities.
    3. Populates dish metadata & logs the cook with rating/notes.
    """
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    input_name = dish_data.name.lower().strip()
    logger.info("Dish log request user_id=%s input=%s", user.id, input_name)
    
    # Precise match check
    dish = db.query(Dish).filter(Dish.name == input_name).first()
    
    # If no precise match, do a strict fuzzy check for typo prevention
    if not dish:
        existing_dishes = db.query(Dish.id, Dish.name).all()
        # Find matches with high confidence (0.85+)
        close_matches = difflib.get_close_matches(
            input_name, 
            [d.name for d in existing_dishes], 
            n=1, 
            cutoff=0.85
        )
        if close_matches:
            matched_name = close_matches[0]
            dish = next(d for d in existing_dishes if d.name == matched_name)
            # Re-fetch the full object
            dish = db.get(Dish, dish.id)
            logger.info("Automatic typo correction: '%s' matched to existing '%s'", input_name, matched_name)

    if not dish:
        logger.info("Creating new canonical dish entry: %s", input_name)
        meal_type = dish_data.meal_type or get_current_meal_type()
        dish = Dish(
            name=input_name,
            dish_type=dish_data.dish_type,
            meal_type=meal_type,
            spiciness=dish_data.spiciness,
            prep_time_minutes=dish_data.prep_time_minutes,
            calories_estimate=dish_data.calories_estimate,
        )
        db.add(dish)
        db.commit()
        db.refresh(dish)
    else:
        logger.debug("Using existing dish: %s", dish.name)

    # Log the CookEvent
    log = CookLog(
        household_id=user.household_id,
        user_id=user.id,
        dish_id=dish.id,
        note=dish_data.note,
        rating=dish_data.rating,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    
    logger.info("Recorded cook event for dish_id=%s rating=%s", dish.id, dish_data.rating)
    return dish
