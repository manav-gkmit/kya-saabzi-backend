from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import TIMESTAMP, Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .common import BaseModel


class RefreshToken(BaseModel):
    """Opaque, DB-backed refresh token for session persistence."""

    __tablename__ = "refresh_tokens"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    revoked_at = Column(TIMESTAMP(timezone=True), nullable=True)

    user = relationship("User")

    @staticmethod
    def hash_token(token: str) -> str:
        """SHA-256 hash of the raw refresh token string."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @property
    def is_expired(self) -> bool:
        expires = self.expires_at
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return datetime.now(UTC) > expires

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_valid(self) -> bool:
        return not self.is_expired and not self.is_revoked
