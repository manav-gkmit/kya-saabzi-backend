"""Tests for app.database.helpers — SQL LIKE escape utility."""
from __future__ import annotations

import pytest

from app.database.helpers import escape_like


class TestEscapeLike:
    """Verify special SQL LIKE characters are escaped correctly."""

    def test_percent_escaped(self) -> None:
        assert escape_like("50%") == "50\\%"

    def test_underscore_escaped(self) -> None:
        assert escape_like("a_b") == "a\\_b"

    def test_backslash_escaped(self) -> None:
        assert escape_like("a\\b") == "a\\\\b"

    def test_multiple_specials(self) -> None:
        assert escape_like("%_\\") == "\\%\\_\\\\"

    def test_clean_string_unchanged(self) -> None:
        assert escape_like("paneer") == "paneer"

    def test_empty_string(self) -> None:
        assert escape_like("") == ""

    def test_custom_escape_char(self) -> None:
        result = escape_like("50%", escape_char="!")
        assert result == "50!%"

    def test_custom_escape_char_underscore(self) -> None:
        result = escape_like("a_b", escape_char="!")
        assert result == "a!_b"

    def test_custom_escape_char_self_escaped(self) -> None:
        result = escape_like("a!b", escape_char="!")
        assert result == "a!!b"

    @pytest.mark.parametrize(
        ("input_str", "expected"),
        [
            ("hello%world", "hello\\%world"),
            ("col_name", "col\\_name"),
            ("100%%", "100\\%\\%"),
            ("no_specials_here", "no\\_specials\\_here"),
        ],
    )
    def test_parametrized_cases(self, input_str: str, expected: str) -> None:
        assert escape_like(input_str) == expected
