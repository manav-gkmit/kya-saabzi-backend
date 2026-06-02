"""Refresh token lifecycle: create, validate-and-rotate, revoke."""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import TokenExpiredError, TokenInvalidError, TokenReuseError
from app.models.refresh_tokens import RefreshToken

ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

logger = logging.getLogger(__name__)


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
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# --- Async refresh token operations ---


async def create_refresh_token(db: AsyncSession, user_id: UUID) -> str:
    """Persist a new refresh token and return the raw (unhashed) value."""
    raw_token = secrets.token_urlsafe(48)
    token_hash = RefreshToken.hash_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
    )

    record = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(record)
    await db.flush()

    logger.info("Refresh token issued user_id=%s", user_id)
    return raw_token


async def validate_and_rotate(db: AsyncSession, raw_token: str) -> tuple[RefreshToken, str]:
    """Validate a refresh token, revoke it, and issue a replacement.

    Returns:
        Tuple of (old RefreshToken record, new raw token string).

    Raises:
        TokenInvalidError: If the token is invalid.
        TokenExpiredError: If the token is expired.
        TokenReuseError: If a revoked token is presented. Before raising, this
            function bulk-revokes all active refresh tokens for the user as a
            safety measure. The caller must commit the session after catching
            this exception so the revocation is persisted.
    """
    token_hash = RefreshToken.hash_token(raw_token)
    # Lock the row so concurrent refresh requests cannot both read revoked_at=NULL
    # and each successfully rotate the same token.
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    result = await db.execute(stmt)
    record = result.scalars().first()

    if not record:
        raise TokenInvalidError("Refresh token not found.")

    if record.is_revoked:
        # Token reuse detected — revoke every token for this user as a safety measure.
        await _revoke_all_for_user(db, record.user_id)
        raise TokenReuseError(record.user_id)

    if record.is_expired:
        raise TokenExpiredError()

    # Rotate: revoke the old token, issue a fresh one
    record.revoked_at = datetime.now(UTC)
    new_raw = await create_refresh_token(db, record.user_id)
    return record, new_raw


async def revoke_token(db: AsyncSession, raw_token: str) -> bool:
    """Revoke a single refresh token (logout). Returns True if revoked."""
    token_hash = RefreshToken.hash_token(raw_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    result = await db.execute(stmt)
    record = result.scalars().first()

    if not record or record.is_revoked:
        return False

    record.revoked_at = datetime.now(UTC)
    await db.flush()
    logger.info("Refresh token revoked user_id=%s", record.user_id)
    return True


async def revoke_all_for_user(db: AsyncSession, user_id: UUID) -> int:
    """Revoke every active refresh token for a user (password change, etc.)."""
    return await _revoke_all_for_user(db, user_id)


async def _revoke_all_for_user(db: AsyncSession, user_id: UUID) -> int:
    """Internal helper — bulk-revoke all active tokens for a user."""
    now = datetime.now(UTC)
    stmt = (
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    result = await db.execute(stmt)
    count = result.rowcount or 0
    await db.flush()
    logger.warning("Bulk-revoked %d refresh tokens user_id=%s", count, user_id)
    return count
