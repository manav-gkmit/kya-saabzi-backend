import logging
import random
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
from app.util import get_current_user, get_current_household

router = APIRouter(prefix="/recommend", tags=["recommendation"])
logger = logging.getLogger(__name__)


def get_current_meal_type() -> str:
    """Helper to determine breakfast/lunch/dinner based on current hour."""
    hour = datetime.now().hour
    if 5 <= hour < 11:
        return "breakfast"
    if 11 <= hour < 16:
        return "lunch"
    if 16 <= hour < 19:
        return "snack"
    return "dinner"


class HybridRecoEngine:
    def __init__(self, db: Session, household_id: str):
        self.db = db
        self.household_id = household_id
        self.household = db.query(Household).get(household_id)

    def get_top_3(self) -> List[RecommendationRead]:
        # 1. Fetch Candidates (Hard Filters)
        # Apply meal_type filter & household dietary preference
        meal_type = get_current_meal_type()
        query = self.db.query(Dish).filter(Dish.meal_type == meal_type)
        
        if self.household and self.household.preferences.get("is_vegetarian"):
            query = query.filter(Dish.dish_type == "veg")

        candidates = query.all()

        # 2. Apply Variety Filter (5-7 day cooldown)
        # We'll use 6 days as the threshold
        cooldown_threshold = datetime.now(timezone.utc) - timedelta(days=6)
        recent_dish_ids = (
            self.db.query(CookLog.dish_id)
            .filter(
                CookLog.household_id == self.household_id,
                CookLog.created_at >= cooldown_threshold
            )
            .all()
        )
        recent_dish_ids = {r[0] for r in recent_dish_ids}

        available_candidates = [c for c in candidates if c.id not in recent_dish_ids]

        if not available_candidates:
            # Fallback: if totally empty, relax the meal_type constraint
            available_candidates = self.db.query(Dish).all()
            available_candidates = [c for c in available_candidates if c.id not in recent_dish_ids]

        # 3. Scoring & Ranking
        # Score = (Global Popularity * 0.2) + (Household History * 0.5) + (Randomness * 0.3)
        scored_dishes = []
        for dish in available_candidates:
            score = self._calculate_score(dish)
            scored_dishes.append((dish, score))

        # Sort by score descending
        scored_dishes.sort(key=lambda x: x[1], reverse=True)
        top_3_dishes = [d[0] for d in scored_dishes[:3]]

        # 4. Construct Results with Notes
        results = []
        for dish in top_3_dishes:
            notes = (
                self.db.query(CookLog.note)
                .filter(CookLog.dish_id == dish.id, CookLog.note.isnot(None))
                .order_by(desc(CookLog.created_at))
                .limit(3)
                .all()
            )
            results.append(
                RecommendationRead(
                    dish=dish, 
                    notes=[n[0] for n in notes]
                )
            )

        return results

    def _calculate_score(self, dish: Dish) -> float:
        # A. Global Popularity (0-10)
        # Count all cooklogs for this dish in last 30 days
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        global_count = (
            self.db.query(func.count(CookLog.id))
            .filter(CookLog.dish_id == dish.id, CookLog.created_at >= thirty_days_ago)
            .scalar() or 0
        )
        pop_score = min(global_count, 10) # Caps at 10

        # B. Household History (0-10)
        # Average rating from this household
        avg_rating = (
            self.db.query(func.avg(CookLog.rating))
            .filter(CookLog.dish_id == dish.id, CookLog.household_id == self.household_id)
            .scalar() or 0.0
        )
        hist_score = float(avg_rating) * 2 # Convert 1-5 to 1-10

        # C. Randomness (0-10)
        rand_score = random.uniform(0, 10)

        total_score = (pop_score * 0.2) + (hist_score * 0.5) + (rand_score * 0.3)
        return total_score


@router.get("/", response_model=List[RecommendationRead])
async def get_recommendation(
    household_id: str = Depends(get_current_household),
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
