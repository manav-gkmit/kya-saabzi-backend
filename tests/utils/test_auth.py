"""Tests for app.utils.auth — get_current_user and get_current_household."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.users import User
from app.utils.auth import get_current_user, get_current_household
from app.utils.jwt import create_access_token


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

    def test_valid_token_returns_user(
        self, db_session: Session, test_user: User,
    ) -> None:
        token = create_access_token(subject=str(test_user.id))
        user = get_current_user(creds=_FakeCreds(credentials=token), db=db_session)
        assert user.id == test_user.id

    def test_no_credentials_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc:
            get_current_user(creds=None, db=None)
        assert exc.value.status_code == 401

    def test_non_bearer_scheme_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc:
            get_current_user(creds=_FakeCreds(scheme="Basic", credentials="x"), db=None)
        assert exc.value.status_code == 401

    def test_invalid_token_raises_401(self, db_session: Session) -> None:
        with pytest.raises(HTTPException) as exc:
            get_current_user(creds=_FakeCreds(credentials="garbage"), db=db_session)
        assert exc.value.status_code == 401

    def test_token_without_sub_raises_401(self, db_session: Session) -> None:
        """A token with no 'sub' claim should be rejected."""
        import jwt as pyjwt
        from app.config import settings

        token = pyjwt.encode(
            {"some": "payload", "exp": 9999999999},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc:
            get_current_user(creds=_FakeCreds(credentials=token), db=db_session)
        assert exc.value.status_code == 401

    def test_non_uuid_sub_raises_401(self, db_session: Session) -> None:
        """A token whose 'sub' is not a valid UUID should be rejected."""
        token = create_access_token(subject="not-a-uuid")
        with pytest.raises(HTTPException) as exc:
            get_current_user(creds=_FakeCreds(credentials=token), db=db_session)
        assert exc.value.status_code == 401

    def test_deleted_user_raises_401(self, db_session: Session) -> None:
        """Token for a user ID that doesn't exist in the DB."""
        fake_id = str(uuid.uuid4())
        token = create_access_token(subject=fake_id)
        with pytest.raises(HTTPException) as exc:
            get_current_user(creds=_FakeCreds(credentials=token), db=db_session)
        assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# get_current_household
# ---------------------------------------------------------------------------


class TestGetCurrentHousehold:
    """Verify household resolution from authenticated user."""

    def test_user_with_household_returns_uuid(self, test_user: User) -> None:
        result = get_current_household(user=test_user)
        assert result == test_user.household_id

    def test_user_without_household_raises_403(self) -> None:
        """A user with household_id=None should get 403."""
        from unittest.mock import MagicMock

        user = MagicMock(spec=User)
        user.household_id = None

        with pytest.raises(HTTPException) as exc:
            get_current_household(user=user)
        assert exc.value.status_code == 403
