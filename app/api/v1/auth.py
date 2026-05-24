import hashlib
import logging
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request, status, Body
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.models.households import Household
from app.models.users import User
from app.schemas.auth import RefreshRequest, Token, TokenRefresh
from app.schemas.users import UserCreate, UserLogin, UserRead
from app.utils.auth import get_current_user
from app.utils.jwt import create_access_token
from app.utils.rate_limit import limiter
from app.utils.security import get_password_hash, verify_password
from app.utils.tokens import (
    TokenReuseError,
    create_refresh_token,
    revoke_all_for_user,
    revoke_token,
    validate_and_rotate,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fingerprint_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _throw_conflict(detail: str, fingerprint: str) -> NoReturn:
    logger.warning("Registration blocked: %s for identifier=%s", detail, fingerprint)
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register_user(
    request: Request,
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    """Register a user and create (or join) a household."""
    fp = _fingerprint_identifier(
        f"{user_data.email.lower()}:{user_data.username.lower()}",
    )

    if db.query(User).filter(User.email == user_data.email).first():
        _throw_conflict("Email already registered.", fp)
    if db.query(User).filter(User.username == user_data.username).first():
        _throw_conflict("Username is already taken.", fp)

    # 1. Resolve household
    if user_data.invite_code:
        invite_code = user_data.invite_code.upper().strip()
        household = db.query(Household).filter(Household.invite_code == invite_code).first()
        if not household:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid invite code provided.",
            )
        is_new_household = False
    else:
        household_name = user_data.household_name or f"{user_data.username}'s Home"
        household = Household(name=household_name)
        db.add(household)
        db.flush()
        is_new_household = True

    # 2. Create user
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        household_id=household.id,
    )
    db.add(user)
    db.flush()

    if is_new_household:
        household.admin_id = user.id

    db.commit()
    db.refresh(user)

    logger.info("User registered user_id=%s household_id=%s", user.id, household.id)
    return user


# ---------------------------------------------------------------------------
# Login / Refresh / Logout
# ---------------------------------------------------------------------------


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
def login_for_access_token(
    request: Request,
    user_data: UserLogin,
    db: Session = Depends(get_db),
):
    """Authenticate and return an access + refresh token pair."""
    identifier = user_data.email or user_data.username
    email_fp = _fingerprint_identifier(identifier.lower())
    logger.info("Login attempt identifier=%s", email_fp)

    if user_data.email:
        user = db.query(User).filter(User.email == user_data.email).first()
    else:
        user = db.query(User).filter(User.username == user_data.username).first()
    if not user or not verify_password(user_data.password, user.hashed_password):  # type: ignore[arg-type]
        logger.warning("Login failed identifier=%s", email_fp)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials provided.",
        )

    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(db, user.id)
    db.commit()

    logger.info("Login successful user_id=%s", user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=TokenRefresh)
@limiter.limit("10/minute")
def refresh_access_token(
    request: Request,
    body: RefreshRequest,
    db: Session = Depends(get_db),
):
    """Exchange a valid refresh token for a new access + refresh pair."""
    try:
        old_record, new_refresh = validate_and_rotate(db, body.refresh_token)
    except TokenReuseError as exc:
        # Commit the bulk-revocation before raising so the DB change is not rolled back.
        db.commit()
        logger.warning("Token reuse detected — user_id=%s, all sessions revoked", exc.user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    access_token = create_access_token(subject=str(old_record.user_id))
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    body: RefreshRequest,
    db: Session = Depends(get_db),
):
    """Revoke the provided refresh token (single-device logout)."""
    revoke_token(db, body.refresh_token)
    db.commit()
    return None


@router.post("/logout/all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all_sessions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke all refresh tokens for the authenticated user (all-device logout)."""
    revoke_all_for_user(db, user.id)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserRead)
def get_current_user_profile(
    user: User = Depends(get_current_user),
):
    """Returns the authenticated user's profile."""
    return user
