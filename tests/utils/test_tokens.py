"""Tests for app.utils.tokens — refresh token create, rotate, revoke."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.refresh_tokens import RefreshToken
from app.models.users import User
from app.utils.tokens import (
    TokenReuseError,
    create_refresh_token,
    revoke_all_for_user,
    revoke_token,
    validate_and_rotate,
)


# ---------------------------------------------------------------------------
# create_refresh_token
# ---------------------------------------------------------------------------


class TestCreateRefreshToken:
    """Verify token creation and persistence."""

    def test_returns_raw_token_string(
        self, db_session: Session, test_user: User,
    ) -> None:
        raw = create_refresh_token(db_session, test_user.id)
        db_session.commit()
        assert isinstance(raw, str)
        assert len(raw) > 0

    def test_db_record_exists_after_creation(
        self, db_session: Session, test_user: User,
    ) -> None:
        raw = create_refresh_token(db_session, test_user.id)
        db_session.commit()

        token_hash = RefreshToken.hash_token(raw)
        record = (
            db_session.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )
        assert record is not None
        assert record.user_id == test_user.id
        assert record.revoked_at is None

    def test_token_hash_matches(
        self, db_session: Session, test_user: User,
    ) -> None:
        raw = create_refresh_token(db_session, test_user.id)
        db_session.commit()

        expected_hash = RefreshToken.hash_token(raw)
        record = (
            db_session.query(RefreshToken)
            .filter(RefreshToken.user_id == test_user.id)
            .first()
        )
        assert record.token_hash == expected_hash


# ---------------------------------------------------------------------------
# validate_and_rotate
# ---------------------------------------------------------------------------


class TestValidateAndRotate:
    """Verify token rotation and reuse detection."""

    def test_valid_token_rotates(
        self, db_session: Session, test_user: User,
    ) -> None:
        raw = create_refresh_token(db_session, test_user.id)
        db_session.commit()

        old_record, new_raw = validate_and_rotate(db_session, raw)
        db_session.commit()

        assert old_record.revoked_at is not None
        assert isinstance(new_raw, str)
        assert new_raw != raw

    def test_unknown_token_raises_value_error(
        self, db_session: Session,
    ) -> None:
        with pytest.raises(ValueError, match="not found"):
            validate_and_rotate(db_session, "totally-fake-token")

    def test_reused_token_raises_token_reuse_error(
        self, db_session: Session, test_user: User,
    ) -> None:
        """Using a token that was already rotated should trigger reuse detection."""
        raw = create_refresh_token(db_session, test_user.id)
        db_session.commit()

        # First rotation — valid
        validate_and_rotate(db_session, raw)
        db_session.commit()

        # Second use of same token — reuse detected
        with pytest.raises(TokenReuseError) as exc:
            validate_and_rotate(db_session, raw)
        assert exc.value.user_id == test_user.id

    def test_reuse_revokes_all_user_sessions(
        self, db_session: Session, test_user: User,
    ) -> None:
        """Token reuse should bulk-revoke every active token for the user."""
        raw1 = create_refresh_token(db_session, test_user.id)
        raw2 = create_refresh_token(db_session, test_user.id)
        db_session.commit()

        # Rotate raw1 first
        validate_and_rotate(db_session, raw1)
        db_session.commit()

        # Reuse raw1 — should revoke everything
        with pytest.raises(TokenReuseError):
            validate_and_rotate(db_session, raw1)
        db_session.commit()

        active = (
            db_session.query(RefreshToken)
            .filter(
                RefreshToken.user_id == test_user.id,
                RefreshToken.revoked_at.is_(None),
            )
            .count()
        )
        assert active == 0

    def test_expired_token_raises_value_error(
        self, db_session: Session, test_user: User,
    ) -> None:
        raw = create_refresh_token(db_session, test_user.id)
        db_session.commit()

        # Manually expire the token
        token_hash = RefreshToken.hash_token(raw)
        record = (
            db_session.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )
        record.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db_session.commit()

        with pytest.raises(ValueError, match="expired"):
            validate_and_rotate(db_session, raw)


# ---------------------------------------------------------------------------
# revoke_token
# ---------------------------------------------------------------------------


class TestRevokeToken:
    """Verify single-token revocation."""

    def test_active_token_revoked(
        self, db_session: Session, test_user: User,
    ) -> None:
        raw = create_refresh_token(db_session, test_user.id)
        db_session.commit()

        result = revoke_token(db_session, raw)
        db_session.commit()

        assert result is True

        token_hash = RefreshToken.hash_token(raw)
        record = (
            db_session.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )
        assert record.revoked_at is not None

    def test_already_revoked_returns_false(
        self, db_session: Session, test_user: User,
    ) -> None:
        raw = create_refresh_token(db_session, test_user.id)
        db_session.commit()

        revoke_token(db_session, raw)
        db_session.commit()

        assert revoke_token(db_session, raw) is False

    def test_unknown_token_returns_false(self, db_session: Session) -> None:
        assert revoke_token(db_session, "nonexistent-token") is False


# ---------------------------------------------------------------------------
# revoke_all_for_user
# ---------------------------------------------------------------------------


class TestRevokeAllForUser:
    """Verify bulk revocation."""

    def test_revokes_all_active_tokens(
        self, db_session: Session, test_user: User,
    ) -> None:
        create_refresh_token(db_session, test_user.id)
        create_refresh_token(db_session, test_user.id)
        create_refresh_token(db_session, test_user.id)
        db_session.commit()

        count = revoke_all_for_user(db_session, test_user.id)
        db_session.commit()

        assert count == 3

        active = (
            db_session.query(RefreshToken)
            .filter(
                RefreshToken.user_id == test_user.id,
                RefreshToken.revoked_at.is_(None),
            )
            .count()
        )
        assert active == 0

    def test_returns_zero_when_no_tokens(self, db_session: Session) -> None:
        count = revoke_all_for_user(db_session, uuid.uuid4())
        assert count == 0


# ---------------------------------------------------------------------------
# TokenReuseError
# ---------------------------------------------------------------------------


class TestTokenReuseError:
    """Verify exception attributes."""

    def test_stores_user_id(self) -> None:
        uid = uuid.uuid4()
        err = TokenReuseError(uid)
        assert err.user_id == uid

    def test_message(self) -> None:
        err = TokenReuseError(uuid.uuid4())
        assert "reuse" in str(err).lower()
