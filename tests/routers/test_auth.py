from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.users import User
from app.utils.security import get_password_hash


def test_register_user(client: TestClient, db_session: Session):
    """
    Test user registration.
    """
    response = client.post(
        "/auth/register",
        json={"username": "testuser", "email": "test@example.com", "password": "password"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"


def test_register_user_existing_email(client: TestClient, db_session: Session):
    """
    Test user registration with an existing email.
    """
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("password"),
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/auth/register",
        json={"username": "newuser", "email": "test@example.com", "password": "password"},
    )
    assert response.status_code == 400


def test_register_user_existing_username(client: TestClient, db_session: Session):
    """
    Test user registration with an existing username.
    """
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("password"),
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/auth/register",
        json={"username": "testuser", "email": "new@example.com", "password": "password"},
    )
    assert response.status_code == 400


def test_login_for_access_token(client: TestClient, db_session: Session):
    """
    Test user login.
    """
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("password"),
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "password"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_for_access_token_invalid_email(client: TestClient, db_session: Session):
    """
    Test user login with an invalid email.
    """
    response = client.post(
        "/auth/login",
        json={"email": "wrong@example.com", "password": "password"},
    )
    assert response.status_code == 401


def test_login_for_access_token_invalid_password(client: TestClient, db_session: Session):
    """
    Test user login with an invalid password.
    """
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("password"),
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
