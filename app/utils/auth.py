"""FastAPI dependencies for authentication and household resolution."""

from __future__ import annotations

import uuid

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    HouseholdAccessDeniedError,
    TokenInvalidError,
    UserNotFoundError,
)
from app.database.db import get_db
from app.models.users import User
from app.utils.tokens import decode_access_token

auth_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Return the authenticated user from the JWT bearer token.

    Raises:
        TokenInvalidError: If credentials are missing, invalid, or the
            corresponding user no longer exists.
        UserNotFoundError: If the user no longer exists.
    """
    if not creds or creds.scheme.lower() != "bearer":
        raise TokenInvalidError("Not authenticated")

    try:
        payload = decode_access_token(creds.credentials)
    except InvalidTokenError as exc:
        raise TokenInvalidError("Invalid or expired token") from exc

    user_id = payload.get("sub")
    if user_id is None:
        raise TokenInvalidError("Invalid token payload")

    try:
        user_id_uuid = uuid.UUID(user_id)
    except ValueError as exc:
        raise TokenInvalidError("Invalid user ID format in token") from exc

    stmt = select(User).where(User.id == user_id_uuid)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise UserNotFoundError()
    return user


async def get_current_household(
    user: User = Depends(get_current_user),
) -> uuid.UUID:
    """Dependency that ensures the user belongs to a household.

    Returns:
        The user's ``household_id``.

    Raises:
        HouseholdAccessDeniedError: If the user has no household assignment.
    """
    if not user.household_id:
        raise HouseholdAccessDeniedError("User does not belong to a household.")
    return user.household_id
