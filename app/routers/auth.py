import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session


from app.utils.jwt import create_access_token
from app.utils.security import verify_password, get_password_hash
from app.schemas.auth import Token
from app.schemas.users import UserCreate, UserRead, UserLogin
from app.models.households import Household
from app.models.users import User
from app.database.db import get_db


router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _fingerprint_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    """
    Registers a user and creates a new household for them.
    In a professional B2B setting, they would then invite family members.
    """
    identifier_fingerprint = _fingerprint_identifier(
        f"{user_data.email.lower()}:{user_data.username.lower()}",
    )
    
    # Validation
    if db.query(User).filter(User.email == user_data.email).first():
        throw_conflict("Email already registered.", identifier_fingerprint)
    if db.query(User).filter(User.username == user_data.username).first():
        throw_conflict("Username is already taken.", identifier_fingerprint)

    # 1. Create a Household first
    household_name = user_data.household_name or f"{user_data.username}'s Home"
    household = Household(name=household_name)
    db.add(household)
    db.flush() # Get the household ID without committing yet

    # 2. Create User and link to household
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        household_id=household.id
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logger.info("User registered and Household created user_id=%s household_id=%s", user.id, household.id)
    return user


def throw_conflict(detail: str, fingerprint: str):
    logger.warning("Registration blocked: %s for identifier=%s", detail, fingerprint)
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def login_for_access_token(
    user_data: UserLogin,
    db: Session = Depends(get_db),
):
    """
    Authenticates a user and returns an access token.

    Args:
        user_data (UserLogin): The user's credentials (email and password).
        db (Session): The database session.

    Raises:
        HTTPException: If the credentials are invalid or the user is not found.

    Returns:
        Token: An object containing the access token and token type.
    """
    email_fingerprint = _fingerprint_identifier(user_data.email.lower())
    logger.info("Login attempt for identifier=%s", email_fingerprint)
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not verify_password(
        user_data.password,
        user.hashed_password,  # type: ignore
    ):
        logger.warning("Login failed for identifier=%s", email_fingerprint)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials provided.",
        )
    access_token = create_access_token(subject=str(user.id))
    logger.info("Login successful user_id=%s", user.id)
    return {"access_token": access_token, "token_type": "bearer"}
