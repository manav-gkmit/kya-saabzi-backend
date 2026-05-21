"""Asynchronous hybrid recommendation engine — scoring and ranking logic."""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cooklogs import CookLog
from app.models.dishes import Dish, Ingredient
from app.models.households import Household
from app.schemas.recommendation import RecommendationRead

logger = logging.getLogger(__name__)
DEFAULT_WINDOW = 6


class AsyncHybridRecoEngine:
    """Multi-signal dish recommender scoped to a single household running asynchronously."""

    def __init__(self, db: AsyncSession, household_id: uuid.UUID, household: Household) -> None:
        self._db = db
        self._household_id = household_id
        self._household = household

    @classmethod
    async def create(cls, db: AsyncSession, household_id: uuid.UUID) -> AsyncHybridRecoEngine:
        household = await db.get(Household, household_id)
        if household is None:
            raise ValueError(f"Household with ID {household_id} not found")
        return cls(db, household_id, household)

    async def get_top_n(self, meal_type: str, *, count: int = 3) -> list[RecommendationRead]:
        """Return the top *count* scored recommendations for *meal_type* asynchronously."""
        candidates = await self._fetch_candidates(meal_type)
        available = await self._apply_cooldown(candidates)
        scored = await self._score_all(available)
        return await self._build_results(scored[:count])

    async def _fetch_candidates(self, meal_type: str) -> list[Dish]:
        stmt = select(Dish).where(
            Dish.meal_type == meal_type,
            (Dish.household_id == self._household_id) | (Dish.household_id.is_(None)),
        )
        prefs = self._household.preferences or {}
        if prefs.get("is_vegetarian"):
            stmt = stmt.where(Dish.dish_type.in_(["veg", "vegan"]))

        avoid = prefs.get("avoid_ingredients")
        if avoid:
            avoid_list = [i.strip().lower() for i in avoid if isinstance(i, str) and i.strip()]
            if avoid_list:
                stmt = stmt.where(
                    ~Dish.ingredients.any(func.lower(Ingredient.name).in_(avoid_list))
                )

        result = await self._db.execute(stmt)
        candidates = result.scalars().all()

        seen: dict[str, Dish] = {}
        for dish in candidates:
            normalized = dish.name.lower()
            if normalized not in seen or (
                seen[normalized].household_id is None and dish.household_id is not None
            ):
                seen[normalized] = dish
        return list(seen.values())

    async def _apply_cooldown(self, candidates: list[Dish]) -> list[Dish]:
        prefs = self._household.preferences or {}
        if prefs.get("include_recently_cooked", False):
            return candidates

        raw_win = prefs.get("recommendation_window_days", DEFAULT_WINDOW)
        try:
            window = max(0, int(raw_win))
        except (ValueError, TypeError):
            window = DEFAULT_WINDOW

        threshold = datetime.now(UTC) - timedelta(days=window)
        stmt = select(CookLog.dish_id).where(
            CookLog.household_id == self._household_id,
            CookLog.created_at >= threshold,
            CookLog.deleted_at.is_(None),
        )
        res = await self._db.execute(stmt)
        recent_ids = set(res.scalars().all())
        return [c for c in candidates if c.id not in recent_ids]

    async def _score_all(self, dishes: list[Dish]) -> list[tuple[Dish, dict[str, float]]]:
        if not dishes:
            return []
        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
        dish_ids = [d.id for d in dishes]

        pop_stmt = (
            select(CookLog.dish_id, func.count(CookLog.id))
            .where(
                CookLog.dish_id.in_(dish_ids),
                CookLog.created_at >= thirty_days_ago,
                CookLog.household_id == self._household_id,
                CookLog.deleted_at.is_(None),
            )
            .group_by(CookLog.dish_id)
        )
        hist_stmt = (
            select(CookLog.dish_id, func.avg(CookLog.rating))
            .where(
                CookLog.dish_id.in_(dish_ids),
                CookLog.household_id == self._household_id,
                CookLog.deleted_at.is_(None),
            )
            .group_by(CookLog.dish_id)
        )

        pop_res, hist_res = await asyncio.gather(
            self._db.execute(pop_stmt), self._db.execute(hist_stmt)
        )
        pop_map = {row[0]: row[1] for row in pop_res.all()}
        hist_map = {row[0]: float(row[1]) for row in hist_res.all() if row[1] is not None}

        scored = []
        for d in dishes:
            pop_val = float(min(pop_map.get(d.id, 0), 10))
            hist_val = float(hist_map.get(d.id, 0.0)) * 2
            rand_val = random.uniform(0, 10)
            total = (pop_val * 0.2) + (hist_val * 0.5) + (rand_val * 0.3)
            scored.append(
                (
                    d,
                    {
                        "popularity": round(pop_val, 2),
                        "history": round(hist_val, 2),
                        "randomness": round(rand_val, 2),
                        "total": round(total, 2),
                    },
                )
            )

        scored.sort(key=lambda x: x[1]["total"], reverse=True)
        return scored

    async def _build_results(
        self, scored: list[tuple[Dish, dict[str, float]]]
    ) -> list[RecommendationRead]:
        results: list[RecommendationRead] = []
        for dish, breakdown in scored:
            stmt = (
                select(CookLog.note)
                .where(
                    CookLog.dish_id == dish.id,
                    CookLog.note.isnot(None),
                    CookLog.household_id == self._household_id,
                )
                .order_by(desc(CookLog.created_at))
                .limit(3)
            )
            res = await self._db.execute(stmt)
            notes = list(res.scalars().all())
            results.append(
                RecommendationRead(
                    dish=dish,
                    notes=notes,
                    score_breakdown=breakdown,
                )
            )
        return results
