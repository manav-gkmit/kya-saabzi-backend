from fastapi import APIRouter, status, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List
import uuid

from app.schemas.cooklogs import CookLogRead
from app.database.db import get_db
from app.deps import get_current_user
from app.models.users import User
from app.models.cooklogs import CookLog


router = APIRouter(prefix="/routers", tags=["logs"])


@router.get("/user/me/logs", response_model=List[CookLogRead])
async def get_my_logs(
    user_data: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logs = (
        db.query(CookLog)
        .options(joinedload(CookLog.dish))
        .filter(CookLog.user_id == user_data.id)
        .all()
    )
    return logs


@router.get("/users/{target_user_id}/logs", response_model=List[CookLogRead])
async def get_user_cooklogs(
    target_user_id: uuid.UUID,
    user_data: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user_data.id != target_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view these logs",
        )
    logs = (
        db.query(CookLog)
        .options(joinedload(CookLog.dish))
        .filter(CookLog.user_id == target_user_id)
        .all()
    )
    return logs
