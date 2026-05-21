from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cooklogs import CookLog


async def create_cook_log_async(
    db: AsyncSession,
    *,
    household_id: UUID,
    user_id: UUID,
    dish_id: UUID,
    note: str | None = None,
    rating: int | None = None,
) -> CookLog:
    """Persist a new cook event asynchronously."""
    log = CookLog(
        household_id=household_id,
        user_id=user_id,
        dish_id=dish_id,
        note=note,
        rating=rating,
    )
    db.add(log)
    await db.flush()
    return log
