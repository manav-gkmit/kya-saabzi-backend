import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.models.cooklogs import CookLog
from app.models.dishes import Dish
from app.models.households import Household
from app.schemas.recommendation import RecommendationRead
from app.util import get_current_user, get_current_household, get_current_meal_type

router = APIRouter(prefix="/recommend", tags=["recommendation"])
logger = logging.getLogger(__name__)


class HybridRecoEngine:
    def __init__(self, db: Session, household_id: uuid.UUID):
        self.db = db
        self.household_id = household_id
        # SQLAlchemy 2.0+ pattern
        self.household = db.get(Household, household_id)

    def get_top_3(self) -> List[RecommendationRead]:
        # 1. Fetch Candidates (Hard Filters)
        # Apply meal_type filter & household dietary preference
        meal_type = get_current_meal_type()
        query = self.db.query(Dish).filter(Dish.meal_type == meal_type)
        
        if self.household and self.household.preferences.get("is_vegetarian"):
            # Include both veg and vegan options
            query = query.filter(Dish.dish_type.in_(["veg", "vegan"]))

        candidates = query.all()

        # 2. Apply Variety Filter (User-defined cooldown window)
        # Defaults to 6 days
        prefs = self.household.preferences if self.household else {}
        include_recent = prefs.get("include_recently_cooked", False)
        window = prefs.get("recommendation_window_days", 6)

        recent_dish_ids = set()
        if not include_recent:
            cooldown_threshold = datetime.now(timezone.utc) - timedelta(days=window)
            results = (
                self.db.query(CookLog.dish_id)
                .filter(
                    CookLog.household_id == self.household_id,
                    CookLog.created_at >= cooldown_threshold
                )
                .all()
            )
            recent_dish_ids = {r[0] for r in results}

        available_candidates = [c for c in candidates if c.id not in recent_dish_ids]

        if not available_candidates:
            # Fallback: if totally empty, relax the meal_type constraint but KEEP dietary constraint
            query = self.db.query(Dish)
            if self.household and self.household.preferences.get("is_vegetarian"):
                query = query.filter(Dish.dish_type.in_(["veg", "vegan"]))

            available_candidates = [c for c in query.all() if c.id not in recent_dish_ids]

        # 3. Scoring & Ranking
        scored_dishes = []
        for dish in available_candidates:
            breakdown = self._calculate_score_breakdown(dish)
            scored_dishes.append((dish, breakdown))

        # Sort by total score descending
        scored_dishes.sort(key=lambda x: x[1]["total"], reverse=True)
        top_3_items = scored_dishes[:3]

        # 4. Construct Results with Notes & Breakdown
        results = []
        for dish, breakdown in top_3_items:
            notes = (
                self.db.query(CookLog.note)
                .filter(
                    CookLog.dish_id == dish.id, 
                    CookLog.note.isnot(None),
                    CookLog.household_id == self.household_id
                )
                .order_by(desc(CookLog.created_at))
                .limit(3)
                .all()
            )
            results.append(
                RecommendationRead(
                    dish=dish, 
                    notes=[n[0] for n in notes],
                    score_breakdown=breakdown
                )
            )

        return results

    def _calculate_score_breakdown(self, dish: Dish) -> dict:
        # A. Global Popularity (0-10)
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        global_count = (
            self.db.query(func.count(CookLog.id))
            .filter(CookLog.dish_id == dish.id, CookLog.created_at >= thirty_days_ago)
            .scalar() or 0
        )
        pop_score = float(min(global_count, 10))

        # B. Household History (0-10)
        avg_rating = (
            self.db.query(func.avg(CookLog.rating))
            .filter(CookLog.dish_id == dish.id, CookLog.household_id == self.household_id)
            .scalar() or 0.0
        )
        hist_score = float(avg_rating) * 2 

        # C. Randomness (0-10)
        rand_score = random.uniform(0, 10)

        total_score = (pop_score * 0.2) + (hist_score * 0.5) + (rand_score * 0.3)
        
        return {
            "popularity": round(pop_score, 2),
            "history": round(hist_score, 2),
            "randomness": round(rand_score, 2),
            "total": round(total_score, 2)
        }


@router.get("/", response_model=List[RecommendationRead])
async def get_recommendation(
    household_id: uuid.UUID = Depends(get_current_household),
    db: Session = Depends(get_db),
):
    """
    Cleaned up Hybrid Recommendation Engine.
    Uses multi-tenant isolation, cooldown filters, and weighted ranking.
    """
    logger.info("Generating reco for household_id=%s", household_id)
    engine = HybridRecoEngine(db, household_id)
    recos = engine.get_top_3()

    if not recos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No recommendations found. Try logging more cooks!"
        )

    return recos
