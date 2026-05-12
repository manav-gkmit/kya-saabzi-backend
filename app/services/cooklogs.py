from uuid import UUID

from sqlalchemy.orm import Session

from app.models.cooklogs import CookLog


def create_cook_log(
    db: Session,
    *,
    household_id: UUID,
    user_id: UUID,
    dish_id: UUID,
    note: str | None = None,
    rating: int | None = None,
) -> CookLog:
    """Persist a new cook event."""
    log = CookLog(
        household_id=household_id,
        user_id=user_id,
        dish_id=dish_id,
        note=note,
        rating=rating,
    )
    db.add(log)
    db.flush()
    return log
