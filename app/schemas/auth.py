from __future__ import annotations

from pydantic import BaseModel, Field

from .users import UserRead


class Token(BaseModel):
    """Returned on login — includes both access and refresh tokens."""

    access_token: str
    refresh_token: str
    user: UserRead
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """Returned on token refresh — no user payload, just new token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Request body for /auth/refresh and /auth/logout."""

    refresh_token: str = Field(..., min_length=1)


class TokenPayload(BaseModel):
    sub: str | None = None
    exp: int | None = None
    jti: str | None = None
