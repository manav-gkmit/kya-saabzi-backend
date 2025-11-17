from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
import uuid
from datetime import datetime, timezone

from app.schemas.cooklogs import CookLogRead
from app.database.db import get_db
from app.util import get_current_user
from app.models.users import User
from app.models.cooklogs import CookLog


router = APIRouter(prefix="/cooklogs", tags=["cooklogs"])


@router.get("/", response_model=List[CookLogRead])
async def get_cooklogs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve all cook logs for the currently authenticated user.

    Args:
        user (User): The currently authenticated user, obtained via dependency
            injection.
        db (Session): The database session, obtained via dependency injection.

    Returns:
        List[CookLogRead]: A list of cook logs for the user, limited to the
            last 7 entries.
    """
    logs = (
        db.query(CookLog)
        .options(joinedload(CookLog.dish))
        .filter(CookLog.user_id == user.id)
        .limit(7)  # Limit to only last 7 logs
        .all()
    )
    return logs


@router.delete("/{cooklog_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cooklog(
    cooklog_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deletes a cooklog entry for the current user.

    Args:
        cooklog_id (uuid.UUID): The ID of the cooklog to delete.
        db (Session): The database session, obtained via dependency injection.
        current_user (User): The currently authenticated user, obtained via
            dependency injection.

    Raises:
        HTTPException: If the cooklog entry is not found for the current user
            (status 404).

    Returns:
        None: Responds with a 204 No Content status upon successful deletion.
    """
    cooklog = db.query(CookLog).filter(
        CookLog.id == cooklog_id,
        CookLog.user_id == current_user.id,
        CookLog.deleted_at.is_(None),
    ).first()

    if not cooklog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cook log entry not found for this user.",
        )

    now = datetime.now(timezone.utc)
    cooklog.deleted_at = now
    db.commit()
    return None
