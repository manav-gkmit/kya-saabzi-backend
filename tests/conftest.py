"""Shared test fixtures — household-aware, compatible with current schema."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.db import get_db
from app.main import app
from app.models.common import Base
from app.models.households import Household
from app.models.users import User
from app.utils.auth import get_current_user
from app.utils.jwt import create_access_token
from app.utils.security import get_password_hash

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
    SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"


def _adapt_datetime_iso(val: datetime) -> str:
    """Store datetimes as ISO-8601 with timezone offset."""
    if val.tzinfo is None:
        val = val.replace(tzinfo=UTC)
    return val.isoformat()


def _convert_timestamp(val: bytes) -> datetime:
    """Read timestamps back as timezone-aware (defaulting to UTC)."""
    dt = datetime.fromisoformat(val.decode())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


sqlite3.register_adapter(datetime, _adapt_datetime_iso)
sqlite3.register_converter("TIMESTAMP", _convert_timestamp)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "detect_types": sqlite3.PARSE_DECLTYPES,
    },
    poolclass=StaticPool,
    native_datetime=True,
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _disable_rate_limit():
    """Disable slowapi rate limiting during tests."""
    from app.utils.rate_limit import limiter

    original = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = original


@pytest.fixture(scope="function")
def db_session():
    """Provide a clean database session per test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session):
    """TestClient with the DB session overridden."""

    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]


# ---------------------------------------------------------------------------
# Household fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_household(db_session: Session) -> Household:
    """A default household with standard preferences."""
    household = Household(name="Test Home")
    db_session.add(household)
    db_session.commit()
    db_session.refresh(household)
    return household


@pytest.fixture()
def other_household(db_session: Session) -> Household:
    """A second, separate household."""
    household = Household(name="Other Home")
    db_session.add(household)
    db_session.commit()
    db_session.refresh(household)
    return household


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_user(db_session: Session, test_household: Household) -> User:
    """Primary test user linked to test_household."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("password"),
        household_id=test_household.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Set user as admin of the household
    test_household.admin_id = user.id
    db_session.commit()
    db_session.refresh(test_household)

    return user


@pytest.fixture()
def other_user(db_session: Session, test_household: Household) -> User:
    """Second user in the same household (not admin)."""
    user = User(
        email="other@example.com",
        username="otheruser",
        hashed_password=get_password_hash("password"),
        household_id=test_household.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def foreign_user(db_session: Session, other_household: Household) -> User:
    """User in a completely different household."""
    user = User(
        email="foreign@example.com",
        username="foreignuser",
        hashed_password=get_password_hash("password"),
        household_id=other_household.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    other_household.admin_id = user.id
    db_session.commit()

    return user


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_headers(test_user: User) -> dict[str, str]:
    """Authorization header with a valid access token for test_user."""
    token = create_access_token(subject=str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def auth_override(test_user: User):
    """Override get_current_user dependency to return test_user.

    Yields the user, then cleans up the override.
    """

    def override():
        return test_user

    app.dependency_overrides[get_current_user] = override
    yield test_user
    del app.dependency_overrides[get_current_user]
