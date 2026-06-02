"""V1 recommendation route — deprecated, internally async."""

import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import HouseholdNotFoundError, NotFoundError
from app.database.db import get_db
from app.schemas.recommendation import RecommendationRead
from app.services.recommendation import HybridRecoEngine
from app.utils.auth import get_current_household
from app.utils.rate_limit import limiter
from app.utils.time import get_current_meal_type

router = APIRouter(prefix="/recommend", tags=["recommendation"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=list[RecommendationRead])
@limiter.limit("10/minute")
async def get_recommendation(
    request: Request,
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"] | None = None,
    household_id: uuid.UUID = Depends(get_current_household),
    db: AsyncSession = Depends(get_db),
):
    """Return top-3 dish recommendations for the household."""
    resolved = meal_type or get_current_meal_type()
    try:
        logger.info(
            "Generating reco for household_id=%s meal_type=%s",
            household_id,
            resolved,
        )

        engine = await HybridRecoEngine.create(db, household_id)
        recos = await engine.get_top_n(resolved)
    except HouseholdNotFoundError as exc:
        raise exc

    if not recos:
        raise NotFoundError("No recommendations found. Try logging more cooks!")

    return recos
