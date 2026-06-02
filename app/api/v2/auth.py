"""Asynchronous authentication router for V2 API."""

import hashlib
import logging
from typing import NoReturn

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import or_, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidCredentialsError, TokenExpiredError, TokenInvalidError, UserAlreadyExistsError
from app.database.db import get_db
from app.models.households import Household
from app.models.users import User
from app.schemas.auth import RefreshRequest, Token, TokenRefresh
from app.schemas.users import UserCreate, UserLogin, UserRead
from app.utils.auth import get_current_user
from app.utils.rate_limit import limiter
from app.utils.security import get_password_hash, verify_password
from app.utils.tokens import (
    TokenReuseError,
    create_access_token,
    create_refresh_token,
    revoke_all_for_user,
    revoke_token,
    validate_and_rotate,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _fingerprint(val: str) -> str:
    return hashlib.sha256(val.encode("utf-8")).hexdigest()[:12]


def _throw_conflict(detail: str, fp: str) -> NoReturn:
    logger.warning("Registration blocked: %s for identifier=%s", detail, fp)
    raise UserAlreadyExistsError(detail)


def _conflict_from_integrity_error(exc: Exception, fp: str) -> NoReturn:
    msg = str(exc).lower()
    if "users_email_key" in msg or "email" in msg:
        _throw_conflict("Email already registered.", fp)
    if "users_username_key" in msg or "username" in msg:
        _throw_conflict("Username is already taken.", fp)
    _throw_conflict("Account already exists.", fp)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register_user(
    request: Request, user_data: UserCreate, db: AsyncSession = Depends(get_db)
):
    """Register a user and create (or join) a household asynchronously."""
    fp = _fingerprint(f"{user_data.email.lower()}:{user_data.username.lower()}")

    existing = (
        (
            await db.execute(
                select(User).where(
                    or_(
                        User.email == user_data.email,
                        User.username == user_data.username,
                    )
                )
            )
        )
        .scalars()
        .first()
    )
    if existing:
        if existing.email == user_data.email:
            _throw_conflict("Email already registered.", fp)
        if existing.username == user_data.username:
            _throw_conflict("Username is already taken.", fp)
        _throw_conflict("Account already exists.", fp)

    if user_data.invite_code:
        code = user_data.invite_code.upper().strip()
        household = (
            (await db.execute(select(Household).where(Household.invite_code == code)))
            .scalars()
            .first()
        )
        if not household:
            raise InvalidCredentialsError()
        is_new = False
    else:
        name = user_data.household_name or f"{user_data.username}'s Home"
        household = Household(name=name)
        db.add(household)
        await db.flush()
        is_new = True

    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        household_id=household.id,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        _conflict_from_integrity_error(exc, fp)
    except DBAPIError as exc:
        await db.rollback()
        _conflict_from_integrity_error(exc, fp)

    if is_new:
        household.admin_id = user.id

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        _conflict_from_integrity_error(exc, fp)
    except DBAPIError as exc:
        await db.rollback()
        _conflict_from_integrity_error(exc, fp)
    await db.refresh(user)
    logger.info("User registered user_id=%s household_id=%s asynchronously", user.id, household.id)
    return user


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
async def login_for_access_token(
    request: Request, user_data: UserLogin, db: AsyncSession = Depends(get_db)
):
    """Authenticate and return an access + refresh token pair asynchronously."""
    identifier = user_data.email or user_data.username
    fp = _fingerprint(identifier.lower())
    logger.info("Login attempt identifier=%s", fp)

    if user_data.email:
        stmt = select(User).where(User.email == user_data.email)
    else:
        stmt = select(User).where(User.username == user_data.username)
    user = (await db.execute(stmt)).scalars().first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        logger.warning("Login failed identifier=%s", fp)
        raise InvalidCredentialsError()

    access_token = create_access_token(subject=str(user.id))
    refresh_token = await create_refresh_token(db, user.id)
    await db.commit()

    logger.info("Login successful user_id=%s asynchronously", user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=TokenRefresh)
@limiter.limit("10/minute")
async def refresh_access_token(
    request: Request, body: RefreshRequest, db: AsyncSession = Depends(get_db)
):
    """Exchange a valid refresh token for a new access + refresh pair asynchronously."""
    try:
        old_record, new_refresh = await validate_and_rotate(db, body.refresh_token)
    except TokenReuseError as exc:
        await db.commit()
        logger.warning("Token reuse detected — user_id=%s, all sessions revoked", exc.user_id)
        raise exc
    except (TokenInvalidError, TokenExpiredError) as exc:
        raise exc

    access_token = create_access_token(subject=str(old_record.user_id))
    await db.commit()
    return {"access_token": access_token, "refresh_token": new_refresh, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Revoke the provided refresh token asynchronously (single-device logout)."""
    await revoke_token(db, body.refresh_token)
    await db.commit()


@router.post("/logout/all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all_sessions(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Revoke all refresh tokens for the authenticated user asynchronously (all-device logout)."""
    await revoke_all_for_user(db, user.id)
    await db.commit()


@router.get("/me", response_model=UserRead)
async def get_current_user_profile(user: User = Depends(get_current_user)):
    """Returns the authenticated user's profile asynchronously."""
    return user
