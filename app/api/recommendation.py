from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.deps import get_current_user
from app.database.db import get_db
from app.models.users import User
from app.models.dishes import Dish
from app.models.cooklogs import CookLog
from app.schemas.dishes import DishRead

router = APIRouter(prefix="/routers", tags=["recommendation"])


@router.get("/recommendation", response_model=DishRead)
async def get_recommendation(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Provides a dish recommendation for the user.

    The recommendation is based on the following logic:
    1.  It will not be a dish the user has cooked in their last 5 meals.
    2.  It will be the most popular dish among other users that the current
        user has not cooked recently.
    3.  If there are no dishes cooked by other users, or the user has
        cooked all of them recently, a 404 error is returned.

    Args:
        user (User): The current authenticated user.
        db (Session): The database session.

    Returns:
        DishRead: The recommended dish.

    Raises:
        HTTPException: If no recommendation is available.
    """
    
    # User's last 5 dishes
    recent_dish_ids = (
        db.query(CookLog.dish_id)
        .filter(CookLog.user_id == user.id)
        .order_by(desc(CookLog.created_at))
        .limit(5)
        .all()
    )
    recent_dish_ids = [d[0] for d in recent_dish_ids]

    # Other's popular dishes
    popular_dishes = (
        db.query(CookLog.dish_id, func.count(CookLog.dish_id))
        .filter(CookLog.user_id != user.id)
        .group_by(CookLog.dish_id)
        .order_by(func.count(CookLog.dish_id).desc())
        .all()
    )

    # Remove user's recent from popular dishes
    for dish_id, _ in popular_dishes:
        if dish_id not in recent_dish_ids:
            recommended_dish = (
                db.query(Dish).filter(Dish.id == dish_id).first()
            )
            if recommended_dish:
                return recommended_dish

    # Return popular dish left else random(kind of)
    if popular_dishes:
        dish_id, _ = popular_dishes[0]
        recommended_dish = db.query(Dish).filter(Dish.id == dish_id).first()
        if recommended_dish:
            return recommended_dish

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No dish recommendations available.",
    )
