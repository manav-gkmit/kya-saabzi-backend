"""Tests for app.utils.time — meal type resolution from hour of day."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from app.utils.time import get_current_meal_type


class TestGetCurrentMealType:
    """Boundary and range tests for meal type resolution."""

    @pytest.mark.parametrize(
        ("hour", "expected"),
        [
            (5, "breakfast"),
            (7, "breakfast"),
            (10, "breakfast"),
            (11, "lunch"),
            (13, "lunch"),
            (15, "lunch"),
            (16, "snack"),
            (17, "snack"),
            (18, "snack"),
            (19, "dinner"),
            (20, "dinner"),
            (23, "dinner"),
            (0, "dinner"),
            (2, "dinner"),
            (4, "dinner"),
        ],
    )
    def test_hour_to_meal_mapping(self, hour: int, expected: str) -> None:
        dt = datetime(2026, 1, 1, hour, 0, tzinfo=timezone.utc)
        assert get_current_meal_type(reference_dt=dt) == expected

    def test_with_reference_dt(self) -> None:
        morning = datetime(2026, 6, 15, 8, 30, tzinfo=timezone.utc)
        assert get_current_meal_type(reference_dt=morning) == "breakfast"

    def test_with_user_tz_converts(self) -> None:
        """A UTC time of 03:00 is 08:30 in IST (+05:30) → breakfast."""
        ist = timezone(timedelta(hours=5, minutes=30))
        utc_time = datetime(2026, 1, 1, 3, 0, tzinfo=timezone.utc)
        result = get_current_meal_type(reference_dt=utc_time, user_tz=ist)
        assert result == "breakfast"

    def test_without_reference_dt_uses_now(self) -> None:
        """When called with no args, should return a valid meal type string."""
        result = get_current_meal_type()
        assert result in {"breakfast", "lunch", "snack", "dinner"}
