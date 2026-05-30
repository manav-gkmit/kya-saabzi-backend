"""Dish search by name with fuzzy matching."""

from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.helpers import escape_like
from app.models.dishes import Dish


async def search_dishes(
    db: AsyncSession,
    query: str,
    *,
    household_id,
    limit: int = 5,
    offset: int = 0,
) -> list[dict]:
    """Return dishes matching *query* ordered by similarity score."""
    safe_q = escape_like(query)
    stmt = (
        select(Dish)
        .where(
            Dish.name.ilike(f"%{safe_q}%", escape="\\"),
            (Dish.household_id == household_id) | (Dish.household_id.is_(None)),
        )
        .order_by(Dish.household_id.is_(None), Dish.name)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    dishes = result.scalars().all()

    scored = []
    for d in dishes:
        ratio = SequenceMatcher(None, query, d.name.lower()).ratio()
        scored.append({"dish": d, "score": round(ratio, 3)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
