"""Time-based helpers for meal type resolution."""
from __future__ import annotations

from datetime import datetime


def get_current_meal_type() -> str:
    """Determine breakfast / lunch / snack / dinner from the current hour."""
    hour = datetime.now().hour

    if 5 <= hour < 11:
        return "breakfast"
    elif 11 <= hour < 16:
        return "lunch"
    elif 16 <= hour < 19:
        return "snack"
    else:
        return "dinner"
