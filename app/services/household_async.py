"""Asynchronous household management business logic."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.households import Household
from app.models.users import User

logger = logging.getLogger(__name__)


async def update_household_preferences_async(
    db: AsyncSession,
    household: Household,
    *,
    name: str | None = None,
    preferences_patch: dict | None = None,
) -> Household:
    """Apply partial updates to a household's name and/or preferences asynchronously.

    Args:
        db: Active async database session.
        household: Household ORM instance to mutate.
        name: New household name (if provided).
        preferences_patch: Dict to shallow-merge into existing preferences.

    Returns:
        The updated household.
    """
    if name:
        household.name = name

    if preferences_patch:
        current = household.preferences or {}
        household.preferences = {**current, **preferences_patch}

    await db.flush()
    return household


async def create_private_household_async(
    db: AsyncSession,
    user: User,
) -> Household:
    """Create a new single-member household for *user* asynchronously.

    Returns:
        The newly created household (flushed but not committed).
    """
    household = Household(
        name=f"{user.username}'s Home",
        admin_id=user.id,
    )
    db.add(household)
    await db.flush()

    user.household_id = household.id
    await db.flush()

    logger.info(
        "Created private household=%s for user=%s asynchronously",
        household.id,
        user.id,
    )
    return household


async def reassign_admin_if_needed_async(
    db: AsyncSession,
    household: Household,
    leaving_user_id: UUID,
) -> None:
    """If *leaving_user_id* is the admin, promote the oldest remaining member asynchronously."""
    if household.admin_id != leaving_user_id:
        return

    stmt = (
        select(User)
        .where(
            User.household_id == household.id,
            User.id != leaving_user_id,
        )
        .order_by(User.created_at.asc())
        .limit(1)
    )
    result = await db.execute(stmt)
    next_admin = result.scalars().first()

    if next_admin:
        household.admin_id = next_admin.id
        await db.flush()
        logger.info(
            "Reassigned admin of household=%s to user=%s asynchronously",
            household.id,
            next_admin.id,
        )


async def cleanup_empty_household_async(db: AsyncSession, household_id: UUID) -> None:
    """Delete a household if it has zero members remaining asynchronously."""
    stmt = select(func.count()).select_from(User).where(User.household_id == household_id)
    result = await db.execute(stmt)
    remaining = result.scalar() or 0

    if remaining == 0:
        old = await db.get(Household, household_id)
        if old:
            await db.delete(old)
            await db.flush()
            logger.info("Deleted empty household=%s asynchronously", household_id)
