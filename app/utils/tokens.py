"""Refresh token lifecycle: create, validate-and-rotate, revoke."""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models.refresh_tokens import RefreshToken


logger = logging.getLogger(__name__)


def create_refresh_token(db: Session, user_id: UUID) -> str:
    """Persist a new refresh token and return the raw (unhashed) value."""
    raw_token = secrets.token_urlsafe(48)
    token_hash = RefreshToken.hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(
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
    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )

    if not record:
        raise ValueError("Refresh token not found.")

    if record.is_revoked:
        # Token reuse detected — revoke every token for this user as a safety measure
        _revoke_all_for_user(db, record.user_id)
        raise ValueError("Token reuse detected. All sessions revoked.")

    if record.is_expired:
        raise ValueError("Refresh token has expired. Please log in again.")

    # Rotate: revoke the old token, issue a fresh one
    record.revoked_at = datetime.now(timezone.utc)
    new_raw = create_refresh_token(db, record.user_id)
    return record, new_raw


def revoke_token(db: Session, raw_token: str) -> bool:
    """Revoke a single refresh token (logout). Returns True if revoked."""
    token_hash = RefreshToken.hash_token(raw_token)
    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )

    if not record or record.is_revoked:
        return False

    record.revoked_at = datetime.now(timezone.utc)
    db.flush()
    logger.info("Refresh token revoked user_id=%s", record.user_id)
    return True


def revoke_all_for_user(db: Session, user_id: UUID) -> int:
    """Revoke every active refresh token for a user (password change, etc.)."""
    return _revoke_all_for_user(db, user_id)


def _revoke_all_for_user(db: Session, user_id: UUID) -> int:
    """Internal helper — bulk-revoke all active tokens for a user."""
    now = datetime.now(timezone.utc)
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
