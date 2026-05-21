"""Refresh token lifecycle: create, validate-and-rotate, revoke."""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import settings
from app.models.refresh_tokens import RefreshToken

logger = logging.getLogger(__name__)


class TokenReuseError(Exception):
    """Raised when a revoked refresh token is presented (possible theft).

    The caller **must** commit the database session before returning a response
    so that the bulk-revocation of all user sessions is persisted.
    """

    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id
        super().__init__("Token reuse detected. All sessions revoked.")


def create_refresh_token(db: Session, user_id: UUID) -> str:
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
    db.flush()

    logger.info("Refresh token issued user_id=%s", user_id)
    return raw_token


def validate_and_rotate(db: Session, raw_token: str) -> tuple[RefreshToken, str]:
    """Validate a refresh token, revoke it, and issue a replacement.

    Returns:
        Tuple of (old RefreshToken record, new raw token string).

    Raises:
        ValueError: If the token is invalid, expired, or already revoked.
    """
    token_hash = RefreshToken.hash_token(raw_token)
    # Lock the row so concurrent refresh requests cannot both read revoked_at=NULL
    # and each successfully rotate the same token.
    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .with_for_update()
        .first()
    )

    if not record:
        raise ValueError("Refresh token not found.")

    if record.is_revoked:
        # Token reuse detected — revoke every token for this user as a safety measure.
        # Raise TokenReuseError so the caller can commit before returning, ensuring
        # the bulk-revocation is not lost on rollback.
        _revoke_all_for_user(db, record.user_id)
        raise TokenReuseError(record.user_id)

    if record.is_expired:
        raise ValueError("Refresh token has expired. Please log in again.")

    # Rotate: revoke the old token, issue a fresh one
    record.revoked_at = datetime.now(UTC)
    new_raw = create_refresh_token(db, record.user_id)
    return record, new_raw


def revoke_token(db: Session, raw_token: str) -> bool:
    """Revoke a single refresh token (logout). Returns True if revoked."""
    token_hash = RefreshToken.hash_token(raw_token)
    record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    if not record or record.is_revoked:
        return False

    record.revoked_at = datetime.now(UTC)
    db.flush()
    logger.info("Refresh token revoked user_id=%s", record.user_id)
    return True


def revoke_all_for_user(db: Session, user_id: UUID) -> int:
    """Revoke every active refresh token for a user (password change, etc.)."""
    return _revoke_all_for_user(db, user_id)


def _revoke_all_for_user(db: Session, user_id: UUID) -> int:
    """Internal helper — bulk-revoke all active tokens for a user."""
    now = datetime.now(UTC)
    count = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .update({"revoked_at": now})
    )
    db.flush()
    logger.warning("Bulk-revoked %d refresh tokens user_id=%s", count, user_id)
    return count


# --- Asynchronous refresh token operations ---


async def create_refresh_token_async(db: AsyncSession, user_id: UUID) -> str:
    """Persist a new refresh token asynchronously and return the raw (unhashed) value."""
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


async def validate_and_rotate_async(db: AsyncSession, raw_token: str) -> tuple[RefreshToken, str]:
    """Validate a refresh token asynchronously, revoke it, and issue a replacement.

    Returns:
        Tuple of (old RefreshToken record, new raw token string).

    Raises:
        ValueError: If the token is invalid, expired, or already revoked.
    """
    token_hash = RefreshToken.hash_token(raw_token)
    # Lock the row so concurrent refresh requests cannot both read revoked_at=NULL
    # and each successfully rotate the same token.
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    result = await db.execute(stmt)
    record = result.scalars().first()

    if not record:
        raise ValueError("Refresh token not found.")

    if record.is_revoked:
        # Token reuse detected — revoke every token for this user as a safety measure.
        await _revoke_all_for_user_async(db, record.user_id)
        raise TokenReuseError(record.user_id)

    if record.is_expired:
        raise ValueError("Refresh token has expired. Please log in again.")

    # Rotate: revoke the old token, issue a fresh one
    record.revoked_at = datetime.now(UTC)
    new_raw = await create_refresh_token_async(db, record.user_id)
    return record, new_raw


async def revoke_token_async(db: AsyncSession, raw_token: str) -> bool:
    """Revoke a single refresh token asynchronously (logout). Returns True if revoked."""
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


async def revoke_all_for_user_async(db: AsyncSession, user_id: UUID) -> int:
    """Revoke every active refresh token for a user asynchronously (password change, etc.)."""
    return await _revoke_all_for_user_async(db, user_id)


async def _revoke_all_for_user_async(db: AsyncSession, user_id: UUID) -> int:
    """Internal helper — bulk-revoke all active tokens for a user asynchronously."""
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
