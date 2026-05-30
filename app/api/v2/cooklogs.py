"""Asynchronous cooklogs HTTP endpoints for V2 API."""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database.db import get_db
from app.models.cooklogs import CookLog
from app.models.users import User
from app.schemas.cooklogs import CookLogRead
from app.utils.auth import get_current_user
from app.utils.rate_limit import get_user_id_or_ip, limiter

router = APIRouter(prefix="/cooklogs", tags=["cooklogs"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=list[CookLogRead])
async def get_cooklogs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Retrieve all cook logs for the currently authenticated user."""
    logger.info("Fetching cook logs for user_id=%s", user.id)
    stmt = (
        select(CookLog)
        .options(joinedload(CookLog.dish))
        .where(CookLog.user_id == user.id, CookLog.deleted_at.is_(None))
        .order_by(CookLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    logs = list(result.scalars().all())
    logger.info("Fetched %s cook logs for user_id=%s", len(logs), user.id)
    return logs


@router.delete("/{cooklog_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def delete_cooklog(
    request: Request,
    cooklog_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deletes a cooklog entry for the current user."""
    stmt = select(CookLog).where(
        CookLog.id == cooklog_id,
        CookLog.household_id == current_user.household_id,
    )
    result = await db.execute(stmt)
    cooklog = result.scalars().first()

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

    cooklog.deleted_at = datetime.now(UTC)
    await db.commit()
    logger.info(
        "Cook log soft-deleted cooklog_id=%s user_id=%s", cooklog_id, current_user.id
    )
