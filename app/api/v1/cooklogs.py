import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session, joinedload

from app.database.db import get_db
from app.models.cooklogs import CookLog
from app.models.users import User
from app.schemas.cooklogs import CookLogRead
from app.utils.auth import get_current_user
from app.utils.rate_limit import get_user_id_or_ip, limiter

router = APIRouter(prefix="/cooklogs", tags=["cooklogs"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=list[CookLogRead])
def get_cooklogs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
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
    logger.info("Fetching cook logs for user_id=%s", user.id)
    logs = (
        db.query(CookLog)
        .options(joinedload(CookLog.dish))
        .filter(CookLog.user_id == user.id)
        .filter(CookLog.deleted_at.is_(None))
        .order_by(CookLog.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    logger.info("Fetched %s cook logs for user_id=%s", len(logs), user.id)
    return logs


@router.delete("/{cooklog_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def delete_cooklog(
    request: Request,
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
    cooklog = (
        db.query(CookLog)
        .filter(
            CookLog.id == cooklog_id,
            CookLog.household_id == current_user.household_id,
        )
        .first()
    )

    if not cooklog or cooklog.deleted_at is not None:
        logger.warning(
            "Cook log delete failed: not found cooklog_id=%s user_id=%s",
            cooklog_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cook log entry not found.",
        )

    if cooklog.user_id != current_user.id:
        logger.warning(
            "Cook log delete forbidden cooklog_id=%s owner_id=%s requester_id=%s",
            cooklog_id,
            cooklog.user_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this cook log entry.",
        )
    now = datetime.now(UTC)
    cooklog.deleted_at = now
    db.commit()
    logger.info("Cook log soft-deleted cooklog_id=%s user_id=%s", cooklog_id, current_user.id)
    return None
