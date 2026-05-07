"""Database query helpers (SQL escaping, etc.)."""

from __future__ import annotations


def escape_like(value: str, escape_char: str = "\\") -> str:
    """Escape special SQL LIKE wildcard characters in user-provided input.

    Escapes ``%``, ``_``, and the escape character itself so they are
    treated as literals inside an ILIKE / LIKE pattern.

    Args:
        value: The raw user input to escape.
        escape_char: The escape character to use in the LIKE pattern
            (must match the ``escape`` argument passed to ``.ilike()``).

    Returns:
        The escaped string, safe to interpolate into a ``%{value}%`` pattern.
    """
    return (
        value.replace(escape_char, escape_char * 2)
        .replace("%", f"{escape_char}%")
        .replace("_", f"{escape_char}_")
    )
