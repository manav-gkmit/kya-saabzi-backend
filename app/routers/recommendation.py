import logging

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List
from datetime import datetime, timedelta, timezone
import random

from app.util import get_current_user
from app.database.db import get_db
from app.models.users import User
from app.models.dishes import Dish
from app.models.cooklogs import CookLog
from app.schemas.recommendation import RecommendationRead

router = APIRouter(prefix="/recommend", tags=["recommendation"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[RecommendationRead])
async def get_recommendation(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Provides dish recommendations for the user.

    The recommendation is based on the following logic:
    1.  It will not be a dish the user has cooked in their last 5 meals.
    2.  It will be the most popular dish among other users that the current
        user has not cooked recently.
    3.  For each recommended dish, it will include up to 3 random notes from
        other users' cooklogs.
    4.  If there are no dishes cooked by other users, or the user has
        cooked all of them recently, a 404 error is returned.

    Args:
        user (User): The current authenticated user.
        db (Session): The database session.

    Returns:
        List[RecommendationRead]: A list of up to 3 recommended dishes with
            random community notes.

    Raises:
        HTTPException: If no recommendation is available.
    """
    logger.info("Generating recommendations for user_id=%s", user.id)
    # User's last 5 dishes
    recent_dish_ids = (
        db.query(CookLog.dish_id)
        .filter(CookLog.user_id == user.id)
        .order_by(desc(CookLog.created_at))
        .limit(5)
        .all()
    )
    recent_dish_ids = [d[0] for d in recent_dish_ids]
    logger.debug("Recent dish ids count=%s for user_id=%s", len(recent_dish_ids), user.id)

    # Other's popular dishes in the last 7 days
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    popular_dishes = (
        db.query(
            CookLog.dish_id,
            func.count(CookLog.dish_id).label("popularity"),
        )
        .filter(
            CookLog.user_id != user.id,
            CookLog.created_at >= seven_days_ago,
        )
        .group_by(CookLog.dish_id)
        .order_by(desc("popularity"))
        .all()
    )
    logger.debug("Popular dish candidates count=%s for user_id=%s", len(popular_dishes), user.id)

    recommendations = []
    for dish_id, _ in popular_dishes:
        if dish_id not in recent_dish_ids:
            dish = db.query(Dish).filter(Dish.id == dish_id).first()
            if dish:
                notes = (
                    db.query(CookLog.note)
                    .filter(
                        CookLog.dish_id == dish_id,
                        CookLog.user_id != user.id,
                        CookLog.note.isnot(None),
                    )
                    .all()
                )
                notes = [n[0] for n in notes]

                if len(notes) > 3:
                    selected_notes = random.sample(notes, 3)
                else:
                    selected_notes = notes

                recommendations.append(
                    RecommendationRead(dish=dish, notes=selected_notes)
                )
                logger.debug("Added recommendation dish_id=%s note_count=%s", dish_id, len(selected_notes))
            if len(recommendations) == 3:
                break

    if not recommendations:
        logger.warning("No recommendations available for user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No dish recommendations available.",
        )

    logger.info("Generated %s recommendations for user_id=%s", len(recommendations), user.id)
    return recommendations
