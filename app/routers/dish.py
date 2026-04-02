import logging

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from app.util import get_current_user
from app.database.db import get_db
from app.schemas.dishes import DishCreate, DishRead
from app.models.users import User
from app.models.dishes import Dish
from app.models.cooklogs import CookLog


router = APIRouter(prefix="/dishes", tags=["dishes"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=DishRead)
async def create_dish(
    dish_data: DishCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Creates a new dish entry if it doesn't exist and logs a cook event for the
        user.

    Args:
        dish_data (DishCreate): The data for the dish to be created or logged.
        user (User): The authenticated user object, obtained from dependency
            injection.
        db (Session): The database session.

    Returns:
        DishRead: The created or existing dish object.

    Raises:
        HTTPException:
            - 401 Unauthorized: If the user is not authenticated.
            - 400 Bad Request: If the dish name contains invalid
                characters (e.g., commas).
    """
    if not user:
        logger.warning("Dish creation attempted without authenticated user")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    dish_name = dish_data.name.lower()
    logger.info("Dish create/log request user_id=%s dish_name=%s", user.id, dish_name)
    dish = db.query(Dish).filter(Dish.name == dish_name).first()
    if not dish:
        logger.info("Creating new dish dish_name=%s", dish_name)
        dish = Dish(
            name=dish_name,
        )
        db.add(dish)
        db.commit()
        db.refresh(dish)
    else:
        logger.debug("Using existing dish dish_id=%s dish_name=%s", dish.id, dish.name)
    log = CookLog(
        user_id=user.id,
        dish_id=dish.id,
        note=dish_data.note,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    logger.info("Cook log created log_id=%s user_id=%s dish_id=%s", log.id, user.id, dish.id)

    return dish
