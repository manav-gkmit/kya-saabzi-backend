"""Household management business logic."""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.households import Household
from app.models.users import User

logger = logging.getLogger(__name__)


def update_household_preferences(
    db: Session,
    household: Household,
    *,
    name: str | None = None,
    preferences_patch: dict | None = None,
) -> Household:
    """Apply partial updates to a household's name and/or preferences.

    Args:
        db: Active database session.
        household: Household ORM instance to mutate.
        name: New household name (if provided).
        preferences_patch: Dict to shallow-merge into existing preferences.

    Returns:
        The updated household (caller should commit).
    """
    if name:
        household.name = name

    if preferences_patch:
        current = household.preferences or {}
        household.preferences = {**current, **preferences_patch}

    db.flush()
    return household


def create_private_household(
    db: Session,
    user: User,
) -> Household:
    """Create a new single-member household for *user*.

    Returns:
        The newly created household (flushed but not committed).
    """
    household = Household(
        name=f"{user.username}'s Home",
        admin_id=user.id,
    )
    db.add(household)
    db.flush()

    user.household_id = household.id
    db.flush()

    logger.info(
        "Created private household=%s for user=%s",
        household.id,
        user.id,
    )
    return household


def reassign_admin_if_needed(
    db: Session,
    household: Household,
    leaving_user_id: UUID,
) -> None:
    """If *leaving_user_id* is the admin, promote the oldest remaining member."""
    if household.admin_id != leaving_user_id:
        return

    next_admin = (
        db.query(User)
        .filter(
            User.household_id == household.id,
            User.id != leaving_user_id,
        )
        .order_by(User.created_at.asc())
        .first()
    )
    if next_admin:
        household.admin_id = next_admin.id
        db.flush()
        logger.info(
            "Reassigned admin of household=%s to user=%s",
            household.id,
            next_admin.id,
        )


def cleanup_empty_household(db: Session, household_id: UUID) -> None:
    """Delete a household if it has zero members remaining."""
    remaining = (
        db.query(User).filter(User.household_id == household_id).count()
    )
    if remaining == 0:
        old = db.get(Household, household_id)
        if old:
            db.delete(old)
            db.flush()
            logger.info("Deleted empty household=%s", household_id)
