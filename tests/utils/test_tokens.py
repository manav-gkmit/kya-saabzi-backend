"""Tests for app.utils.tokens — refresh token create, rotate, revoke."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_tokens import RefreshToken
from app.models.users import User
from app.utils.tokens import (
    TokenReuseError,
    create_refresh_token,
    revoke_all_for_user,
    revoke_token,
    validate_and_rotate,
)

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# create_refresh_token
# ---------------------------------------------------------------------------


class TestCreateRefreshToken:
    """Verify token creation and persistence."""

    async def test_returns_raw_token_string(
        self,
        async_db_session: AsyncSession,
        async_test_user: User,
    ) -> None:
        raw = await create_refresh_token(async_db_session, async_test_user.id)
        await async_db_session.commit()
        assert isinstance(raw, str)
        assert len(raw) > 0

    async def test_db_record_exists_after_creation(
        self,
        async_db_session: AsyncSession,
        async_test_user: User,
    ) -> None:
        raw = await create_refresh_token(async_db_session, async_test_user.id)
        await async_db_session.commit()

        token_hash = RefreshToken.hash_token(raw)
        result = await async_db_session.execute(select(RefreshToken).filter(RefreshToken.token_hash == token_hash))
        record = result.scalars().first()
        
        assert record is not None
        assert record.user_id == async_test_user.id
        assert record.revoked_at is None

    async def test_token_hash_matches(
        self,
        async_db_session: AsyncSession,
        async_test_user: User,
    ) -> None:
        raw = await create_refresh_token(async_db_session, async_test_user.id)
        await async_db_session.commit()

        expected_hash = RefreshToken.hash_token(raw)
        result = await async_db_session.execute(select(RefreshToken).filter(RefreshToken.user_id == async_test_user.id))
        record = result.scalars().first()
        assert record.token_hash == expected_hash


# ---------------------------------------------------------------------------
# validate_and_rotate
# ---------------------------------------------------------------------------


class TestValidateAndRotate:
    """Verify token rotation and reuse detection."""

    async def test_valid_token_rotates(
        self,
        async_db_session: AsyncSession,
        async_test_user: User,
    ) -> None:
        raw = await create_refresh_token(async_db_session, async_test_user.id)
        await async_db_session.commit()

        old_record, new_raw = await validate_and_rotate(async_db_session, raw)
        await async_db_session.commit()

        assert old_record.revoked_at is not None
        assert isinstance(new_raw, str)
        assert new_raw != raw

    async def test_unknown_token_raises_value_error(
        self,
        async_db_session: AsyncSession,
    ) -> None:
        with pytest.raises(ValueError, match="not found"):
            await validate_and_rotate(async_db_session, "totally-fake-token")

    async def test_reused_token_raises_token_reuse_error(
        self,
        async_db_session: AsyncSession,
        async_test_user: User,
    ) -> None:
        """Using a token that was already rotated should trigger reuse detection."""
        raw = await create_refresh_token(async_db_session, async_test_user.id)
        await async_db_session.commit()

        # First rotation — valid
        await validate_and_rotate(async_db_session, raw)
        await async_db_session.commit()

        # Second use of same token — reuse detected
        with pytest.raises(TokenReuseError) as exc:
            await validate_and_rotate(async_db_session, raw)
        assert exc.value.user_id == async_test_user.id

    async def test_reuse_revokes_all_user_sessions(
        self,
        async_db_session: AsyncSession,
        async_test_user: User,
    ) -> None:
        """Token reuse should bulk-revoke every active token for the user."""
        raw1 = await create_refresh_token(async_db_session, async_test_user.id)
        await create_refresh_token(async_db_session, async_test_user.id)
        await async_db_session.commit()

        # Rotate raw1 first
        await validate_and_rotate(async_db_session, raw1)
        await async_db_session.commit()

        # Reuse raw1 — should revoke everything
        with pytest.raises(TokenReuseError):
            await validate_and_rotate(async_db_session, raw1)
        await async_db_session.commit()

        result = await async_db_session.execute(
            select(func.count()).select_from(RefreshToken).filter(
                RefreshToken.user_id == async_test_user.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        active = result.scalar()
        assert active == 0

    async def test_expired_token_raises_value_error(
        self,
        async_db_session: AsyncSession,
        async_test_user: User,
    ) -> None:
        raw = await create_refresh_token(async_db_session, async_test_user.id)
        await async_db_session.commit()

        # Manually expire the token
        token_hash = RefreshToken.hash_token(raw)
        result = await async_db_session.execute(select(RefreshToken).filter(RefreshToken.token_hash == token_hash))
        record = result.scalars().first()
        record.expires_at = datetime.now(UTC) - timedelta(hours=1)
        await async_db_session.commit()

        with pytest.raises(ValueError, match="expired"):
            await validate_and_rotate(async_db_session, raw)


# ---------------------------------------------------------------------------
# revoke_token
# ---------------------------------------------------------------------------


class TestRevokeToken:
    """Verify single-token revocation."""

    async def test_active_token_revoked(
        self,
        async_db_session: AsyncSession,
        async_test_user: User,
    ) -> None:
        raw = await create_refresh_token(async_db_session, async_test_user.id)
        await async_db_session.commit()

        result = await revoke_token(async_db_session, raw)
        await async_db_session.commit()

        assert result is True

        token_hash = RefreshToken.hash_token(raw)
        result2 = await async_db_session.execute(select(RefreshToken).filter(RefreshToken.token_hash == token_hash))
        record = result2.scalars().first()
        assert record.revoked_at is not None

    async def test_already_revoked_returns_false(
        self,
        async_db_session: AsyncSession,
        async_test_user: User,
    ) -> None:
        raw = await create_refresh_token(async_db_session, async_test_user.id)
        await async_db_session.commit()

        await revoke_token(async_db_session, raw)
        await async_db_session.commit()

        assert await revoke_token(async_db_session, raw) is False

    async def test_unknown_token_returns_false(self, async_db_session: AsyncSession) -> None:
        assert await revoke_token(async_db_session, "nonexistent-token") is False


# ---------------------------------------------------------------------------
# revoke_all_for_user
# ---------------------------------------------------------------------------


class TestRevokeAllForUser:
    """Verify bulk revocation."""

    async def test_revokes_all_active_tokens(
        self,
        async_db_session: AsyncSession,
        async_test_user: User,
    ) -> None:
        await create_refresh_token(async_db_session, async_test_user.id)
        await create_refresh_token(async_db_session, async_test_user.id)
        await create_refresh_token(async_db_session, async_test_user.id)
        await async_db_session.commit()

        count = await revoke_all_for_user(async_db_session, async_test_user.id)
        await async_db_session.commit()

        assert count == 3

        result = await async_db_session.execute(
            select(func.count()).select_from(RefreshToken).filter(
                RefreshToken.user_id == async_test_user.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        active = result.scalar()
        assert active == 0

    async def test_returns_zero_when_no_tokens(self, async_db_session: AsyncSession) -> None:
        count = await revoke_all_for_user(async_db_session, uuid.uuid4())
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
