"""Hybrid recommendation engine — scoring and ranking logic."""
from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.cooklogs import CookLog
from app.models.dishes import Dish
from app.models.households import Household
from app.schemas.recommendation import RecommendationRead

logger = logging.getLogger(__name__)

_DEFAULT_WINDOW_DAYS = 6


class HybridRecoEngine:
    """Multi-signal dish recommender scoped to a single household."""

    def __init__(self, db: Session, household_id: uuid.UUID) -> None:
        self._db = db
        self._household_id = household_id
        self._household = db.get(Household, household_id)
        if self._household is None:
            raise ValueError(f"Household with ID {household_id} not found")

    def get_top_n(
        self,
        meal_type: str,
        *,
        count: int = 3,
    ) -> list[RecommendationRead]:
        """Return the top *count* scored recommendations for *meal_type*."""
        candidates = self._fetch_candidates(meal_type)
        available = self._apply_cooldown(candidates)
        scored = self._score_all(available)
        return self._build_results(scored[:count])

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_candidates(self, meal_type: str) -> list[Dish]:
        query = self._db.query(Dish).filter(
            Dish.meal_type == meal_type,
            (Dish.household_id == self._household_id) | (Dish.household_id.is_(None))
        )

        prefs = self._prefs()
        if prefs.get("is_vegetarian"):
            query = query.filter(Dish.dish_type.in_(["veg", "vegan"]))

        return query.all()

    def _apply_cooldown(self, candidates: list[Dish]) -> list[Dish]:
        prefs = self._prefs()
        if prefs.get("include_recently_cooked", False):
            return candidates

        window = self._safe_window(prefs)
        threshold = datetime.now(timezone.utc) - timedelta(days=window)

        recent_ids = {
            row[0]
            for row in (
                self._db.query(CookLog.dish_id)
                .filter(
                    CookLog.household_id == self._household_id,
                    CookLog.created_at >= threshold,
                    CookLog.deleted_at.is_(None),
                )
                .all()
            )
        }
        return [c for c in candidates if c.id not in recent_ids]

    def _score_all(
        self,
        dishes: list[Dish],
    ) -> list[tuple[Dish, dict]]:
        scored = [
            (d, self._score_breakdown(d)) for d in dishes
        ]
        scored.sort(key=lambda x: x[1]["total"], reverse=True)
        return scored

    def _score_breakdown(self, dish: Dish) -> dict:
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        global_count = (
            self._db.query(func.count(CookLog.id))
            .filter(
                CookLog.dish_id == dish.id,
                CookLog.created_at >= thirty_days_ago,
            )
            .scalar()
            or 0
        )
        pop_score = float(min(global_count, 10))

        avg_rating = (
            self._db.query(func.avg(CookLog.rating))
            .filter(
                CookLog.dish_id == dish.id,
                CookLog.household_id == self._household_id,
            )
            .scalar()
            or 0.0
        )
        hist_score = float(avg_rating) * 2

        rand_score = random.uniform(0, 10)

        total = (pop_score * 0.2) + (hist_score * 0.5) + (rand_score * 0.3)

        return {
            "popularity": round(pop_score, 2),
            "history": round(hist_score, 2),
            "randomness": round(rand_score, 2),
            "total": round(total, 2),
        }

    def _build_results(
        self,
        scored: list[tuple[Dish, dict]],
    ) -> list[RecommendationRead]:
        results: list[RecommendationRead] = []
        for dish, breakdown in scored:
            notes = (
                self._db.query(CookLog.note)
                .filter(
                    CookLog.dish_id == dish.id,
                    CookLog.note.isnot(None),
                    CookLog.household_id == self._household_id,
                )
                .order_by(desc(CookLog.created_at))
                .limit(3)
                .all()
            )
            results.append(
                RecommendationRead(
                    dish=dish,
                    notes=[n[0] for n in notes],
                    score_breakdown=breakdown,
                ),
            )
        return results

    # ------------------------------------------------------------------
    # Tiny helpers
    # ------------------------------------------------------------------

    def _prefs(self) -> dict:
        if not self._household:
            return {}
        return self._household.preferences or {}

    @staticmethod
    def _safe_window(prefs: dict) -> int:
        raw = prefs.get("recommendation_window_days", _DEFAULT_WINDOW_DAYS)
        try:
            return max(0, int(raw))
        except (ValueError, TypeError):
            return _DEFAULT_WINDOW_DAYS
