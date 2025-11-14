from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_current_user
from app.database.db import get_db
from app.schemas.dishes import DishCreate, DishRead
from app.models.users import User
from app.models.dishes import Dish
from app.models.cooklogs import CookLog


router = APIRouter(prefix="/routers", tags=["create_dish"])


@router.post("/add_dish", response_model=DishRead)
async def create_dish(
    dish_data: DishCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    dish = db.query(Dish).filter(Dish.name == dish_data.name).first()
    if not dish:
        dish = Dish(
            name=dish_data.name,
        )
        db.add(dish)
        db.commit()
        db.refresh(dish)
    log = CookLog(
        user_id=user.id,
        dish_id=dish.id,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return dish
