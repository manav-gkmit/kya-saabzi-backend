from fastapi import APIRouter, status, HTTPException, Depends
from sqlalchemy import desc
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
    """
    Retrieve all cook logs for the currently authenticated user.

    Args:
        user_data (User): The authenticated user object, obtained from
        dependency injection.
        db (Session): The database session.

    Returns:
        List[CookLogRead]: A list of cook log entries, including associated
        dish information.

    Raises:
        HTTPException: If the user is not authenticated
        (handled by get_current_user dependency).
    """
    logs = (
        db.query(CookLog)
        .options(joinedload(CookLog.dish))
        .filter(CookLog.user_id == user_data.id)
        .order_by(desc(CookLog.created_at))
        .limit(7)  # Limit to only last 7 logs
        .all()
    )
    return logs


@router.get("/users/{target_user_id}/logs", response_model=List[CookLogRead])
async def get_user_cooklogs(
    target_user_id: uuid.UUID,
    user_data: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve cook logs for a specific user, with authorization check.

    Args:
        target_user_id (uuid.UUID): The UUID of the user whose logs are
            to be retrieved.
        user_data (User): The authenticated user object, obtained from
            dependency injection.
        db (Session): The database session.

    Returns:
        List[CookLogRead]: A list of cook log entries for the target user,
            including associated dish information.

    Raises:
        HTTPException:
            - 401 Unauthorized: If the user is not authenticated (handled by
                get_current_user dependency).
            - 403 Forbidden: If the authenticated user attempts to view
                logs of another user.
    """
    if user_data.id != target_user_id:  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view these logs",
        )
    logs = (
        db.query(CookLog)
        .options(joinedload(CookLog.dish))
        .filter(CookLog.user_id == target_user_id)
        .limit(7)
        .all()
    )
    return logs
