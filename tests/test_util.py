from sqlalchemy.orm import Session
import pytest
import uuid
from fastapi import HTTPException, status
from app.utils.auth import get_current_user
from app.models.users import User
from app.utils.jwt import create_access_token, decode_access_token
from jose import jwt, JWTError

def test_get_current_user(db_session: Session):
    """
    Test getting the current user with a valid token.
    """
    user = User(
        username="testuser", 
        email="test@example.com", 
        hashed_password="password",
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(subject=str(user.id))
    
    class MockCreds:
        scheme = "Bearer"
        credentials = token

    current_user = get_current_user(creds=MockCreds(), db=db_session)
    assert current_user.id == user.id


def test_get_current_user_no_creds():
    """
    Test getting the current user with no credentials.
    """
    with pytest.raises(HTTPException) as excinfo:
        get_current_user(creds=None, db=None)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_non_bearer():
    """
    Test getting the current user with a non-bearer token.
    """
    class MockCreds:
        scheme = "Non-Bearer"
        credentials = "token"

    with pytest.raises(HTTPException) as excinfo:
        get_current_user(creds=MockCreds(), db=None)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_invalid_token(db_session: Session):
    """
    Test getting the current user with an invalid token.
    """
    class MockCreds:
        scheme = "Bearer"
        credentials = "invalid_token"

    with pytest.raises(HTTPException) as excinfo:
        get_current_user(creds=MockCreds(), db=db_session)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_no_sub(db_session: Session):
    """
    Test getting the current user with a token that has no sub claim.
    """
    token = jwt.encode({"some": "payload"}, "secret", algorithm="HS256")

    class MockCreds:
        scheme = "Bearer"
        credentials = token

    with pytest.raises(HTTPException) as excinfo:
        get_current_user(creds=MockCreds(), db=db_session)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_non_existent_user(db_session: Session):
    """
    Test getting the current user with a token for a non-existent user.
    """
    token = create_access_token(subject=str(uuid.uuid4()))

    class MockCreds:
        scheme = "Bearer"
        credentials = token

    with pytest.raises(HTTPException) as excinfo:
        get_current_user(creds=MockCreds(), db=db_session)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_decode_access_token_jwt_error():
    """
    Test decoding an invalid access token to trigger a JWTError.
    """
    with pytest.raises(JWTError):
        decode_access_token("invalid_token")
