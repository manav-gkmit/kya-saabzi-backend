"""Recommendation HTTP endpoint — thin adapter over the engine service."""

import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

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
def get_recommendation(
    request: Request,
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"] | None = None,
    household_id: uuid.UUID = Depends(get_current_household),
    db: Session = Depends(get_db),
):
    """Return top-3 dish recommendations for the household."""
    resolved = meal_type or get_current_meal_type()
    logger.info(
        "Generating reco for household_id=%s meal_type=%s",
        household_id,
        resolved,
    )

    engine = HybridRecoEngine(db, household_id)
    recos = engine.get_top_n(resolved)

    if not recos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No recommendations found. Try logging more cooks!",
        )

    return recos
