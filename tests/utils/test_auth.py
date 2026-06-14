"""Tests for app.utils.auth — get_current_user and get_current_household."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import HouseholdAccessDeniedError, TokenInvalidError
from app.models.users import User
from app.utils.auth import get_current_household, get_current_user
from app.utils.tokens import create_access_token

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeCreds:
    """Minimal stand-in for HTTPAuthorizationCredentials."""

    def __init__(self, scheme: str = "Bearer", credentials: str = "") -> None:
        self.scheme = scheme
        self.credentials = credentials


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------


class TestGetCurrentUser:
    """Verify JWT-based user resolution."""

    async def test_valid_token_returns_user(
        self,
        async_db_session: AsyncSession,
        async_test_user: User,
    ) -> None:
        token = create_access_token(subject=str(async_test_user.id))
        user = await get_current_user(creds=_FakeCreds(credentials=token), db=async_db_session)
        assert user.id == async_test_user.id

    async def test_no_credentials_raises_401(self) -> None:
        with pytest.raises(TokenInvalidError, match="Not authenticated"):
            await get_current_user(creds=None, db=None)

    async def test_non_bearer_scheme_raises_401(self) -> None:
        with pytest.raises(TokenInvalidError, match="Not authenticated"):
            await get_current_user(creds=_FakeCreds(scheme="Basic", credentials="x"), db=None)

    async def test_invalid_token_raises_401(self, async_db_session: AsyncSession) -> None:
        with pytest.raises(TokenInvalidError, match="Invalid or expired token"):
            await get_current_user(creds=_FakeCreds(credentials="garbage"), db=async_db_session)

    async def test_token_without_sub_raises_401(self, async_db_session: AsyncSession) -> None:
        """A token with no 'sub' claim should be rejected."""
        import jwt as pyjwt

        from app.config import settings

        token = pyjwt.encode(
            {"some": "payload", "exp": 9999999999},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        with pytest.raises(TokenInvalidError, match="Invalid token payload"):
            await get_current_user(creds=_FakeCreds(credentials=token), db=async_db_session)

    async def test_non_uuid_sub_raises_401(self, async_db_session: AsyncSession) -> None:
        """A token whose 'sub' is not a valid UUID should be rejected."""
        token = create_access_token(subject="not-a-uuid")
        with pytest.raises(TokenInvalidError, match="Invalid user ID format"):
            await get_current_user(creds=_FakeCreds(credentials=token), db=async_db_session)

    async def test_non_string_sub_raises_401(self, async_db_session: AsyncSession) -> None:
        """A token whose 'sub' is an integer (not a string) should be rejected."""
        import jwt as pyjwt

        from app.config import settings

        token = pyjwt.encode(
            {"sub": 123, "exp": 9999999999},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        with pytest.raises(TokenInvalidError):
            await get_current_user(creds=_FakeCreds(credentials=token), db=async_db_session)

    async def test_deleted_user_raises_401(self, async_db_session: AsyncSession) -> None:
        """Token for a user ID that doesn't exist in the DB."""
        fake_id = str(uuid.uuid4())
        token = create_access_token(subject=fake_id)
        with pytest.raises(TokenInvalidError, match="User not found"):
            await get_current_user(creds=_FakeCreds(credentials=token), db=async_db_session)


# ---------------------------------------------------------------------------
# get_current_household
# ---------------------------------------------------------------------------


class TestGetCurrentHousehold:
    """Verify household resolution from authenticated user."""

    async def test_user_with_household_returns_uuid(self, async_test_user: User) -> None:
        result = await get_current_household(user=async_test_user)
        assert result == async_test_user.household_id

    async def test_user_without_household_raises_403(self) -> None:
        """A user with household_id=None should get HouseholdAccessDeniedError."""
        from unittest.mock import MagicMock

        user = MagicMock(spec=User)
        user.household_id = None

        with pytest.raises(HouseholdAccessDeniedError):
            await get_current_household(user=user)
