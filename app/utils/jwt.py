from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid
from jose import jwt, JWTError

from app.config import settings

ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
    include_jti: bool = False,
) -> str:
    """
    Creates a new access token.

    Args:
        subject (str): The subject of the token.
        expires_delta (Optional[timedelta], optional): The token's expiration
            delta. Defaults to None.
        include_jti (bool, optional): Whether to include a unique token
            identifier. Defaults to False.

    Returns:
        str: The encoded access token.
    """
    now = datetime.now(timezone.utc)
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    if include_jti:
        payload["jti"] = str(uuid.uuid4())
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def decode_access_token(token: str) -> dict:
    """
    Decodes an access token.

    Args:
        token (str): The encoded access token.

    Raises:
        JWTError: If the token is invalid or expired.

    Returns:
        dict: The token's payload.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise
