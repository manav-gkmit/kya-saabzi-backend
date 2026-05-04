"""Shared rate limiter instance for the application."""
from __future__ import annotations

from starlette.requests import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


def get_user_id_or_ip(request: Request) -> str:
    """Extract user ID from JWT for per-user rate limiting.

    Falls back to remote IP if the token is missing or invalid.
    """
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1]
        try:
            from app.utils.jwt import decode_access_token
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            if user_id:
                return user_id
        except Exception:
            pass
    return get_remote_address(request)

