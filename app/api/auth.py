from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session


from app.utils.jwt import create_access_token
from app.utils.security import verify_password, get_password_hash
from app.schemas.auth import Token
from app.schemas.users import UserCreate, UserRead, UserLogin
from app.models.users import User
from app.database.db import get_db


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead)
async def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    """
    Registers a user and returns the entry in the database.

    Args:
        user_data (UserCreate): The user's credentials (email and password).
        db (Session): The database session.

    Raises:
        HTTPException: If matching entries for either email or username are
            found.

    Returns:
        Token: An object containing the access token and token type.
    """
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered.",
        )
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already taken.",
        )
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(
            user_data.password,
        ),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
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
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not verify_password(
        user_data.password,
        user.hashed_password,  # type: ignore
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials provided.",
        )
    access_token = create_access_token(subject=str(user.id))
    return {"access_token": access_token, "token_type": "bearer"}
