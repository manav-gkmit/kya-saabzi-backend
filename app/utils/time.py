"""Time-based helpers for meal type resolution."""
from __future__ import annotations

from datetime import datetime, tzinfo


def get_current_meal_type(
    *,
    reference_dt: datetime | None = None,
    user_tz: tzinfo | None = None,
) -> str:
    """Determine breakfast / lunch / snack / dinner from the current hour.
    
    Args:
        reference_dt: Optional aware datetime to resolve hour from.
        user_tz: Optional timezone to use with datetime.now().
    """
    if reference_dt:
        if user_tz:
            hour = reference_dt.astimezone(user_tz).hour
        else:
            hour = reference_dt.hour
    else:
        hour = datetime.now(user_tz).hour

    if 5 <= hour < 11:
        return "breakfast"
    elif 11 <= hour < 16:
        return "lunch"
    elif 16 <= hour < 19:
        return "snack"
    else:
        return "dinner"
