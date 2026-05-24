"""Asynchronous recommendation HTTP endpoint for V2 API."""

import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_async_db
from app.schemas.recommendation import RecommendationRead
from app.services.recommendation_async import AsyncHybridRecoEngine
from app.utils.auth import get_current_household_async
from app.utils.rate_limit import limiter
from app.utils.time import get_current_meal_type

router = APIRouter(prefix="/recommend", tags=["recommendation"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=list[RecommendationRead])
@limiter.limit("10/minute")
async def get_recommendation(
    request: Request,
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"] | None = None,
    household_id: uuid.UUID = Depends(get_current_household_async),
    db: AsyncSession = Depends(get_async_db),
):
    """Return top-3 dish recommendations asynchronously for the household."""
    resolved = meal_type or get_current_meal_type()
    logger.info(
        "Generating reco asynchronously for household_id=%s meal_type=%s",
        household_id,
        resolved,
    )

    try:
        engine = await AsyncHybridRecoEngine.create(db, household_id)
        recos = await engine.get_top_n(resolved)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    if not recos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No recommendations found. Try logging more cooks!",
        )

    return recos
