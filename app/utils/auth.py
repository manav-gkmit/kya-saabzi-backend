"""FastAPI dependencies for authentication and household resolution."""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.database.db import get_async_db, get_db
from app.models.users import User
from app.utils.tokens import decode_access_token

auth_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return the authenticated user from the JWT bearer token.

    Raises:
        HTTPException: 401 if credentials are missing, invalid, or the
            corresponding user no longer exists.
    """
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = decode_access_token(creds.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user_id_uuid = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format in token",
        ) from exc

    user = db.query(User).filter(User.id == user_id_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def get_current_household(
    user: User = Depends(get_current_user),
) -> uuid.UUID:
    """Dependency that ensures the user belongs to a household.

    Returns:
        The user's ``household_id``.

    Raises:
        HTTPException: 403 if the user has no household assignment.
    """
    if not user.household_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to a household.",
        )
    return user.household_id


# --- Asynchronous authentication dependencies ---


async def get_current_user_async(
    creds: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: AsyncSession = Depends(get_async_db),
) -> User:
    """Return the authenticated user asynchronously from the JWT bearer token.

    Raises:
        HTTPException: 401 if credentials are missing, invalid, or the
            corresponding user no longer exists.
    """
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = decode_access_token(creds.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user_id_uuid = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format in token",
        ) from exc

    stmt = select(User).where(User.id == user_id_uuid)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


async def get_current_household_async(
    user: User = Depends(get_current_user_async),
) -> uuid.UUID:
    """Dependency that ensures the user belongs to a household asynchronously.

    Returns:
        The user's ``household_id``.

    Raises:
        HTTPException: 403 if the user has no household assignment.
    """
    if not user.household_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to a household.",
        )
    return user.household_id
