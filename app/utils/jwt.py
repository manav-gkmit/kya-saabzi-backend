"""Access token creation and decoding using PyJWT."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.config import settings

ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    include_jti: bool = False,
) -> str:
    """Create a signed JWT access token.

    Args:
        subject: The token subject (typically user ID).
        expires_delta: Custom expiry. Defaults to ACCESS_TOKEN_EXPIRE_MINUTES.
        include_jti: Whether to add a unique token identifier claim.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(UTC)
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    if include_jti:
        payload["jti"] = str(uuid.uuid4())
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT access token.

    Raises:
        jwt.InvalidTokenError: If the token is malformed, expired, or tampered.
    """
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        raise
