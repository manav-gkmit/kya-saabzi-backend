"""Shared test fixtures — household-aware, compatible with current schema."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.db import get_db
from app.main import app
from app.models.common import Base
from app.models.households import Household
from app.models.users import User
from app.utils.auth import get_current_user
from app.utils.tokens import create_access_token
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



# ---------------------------------------------------------------------------
# Async fixtures for V2 endpoints
# ---------------------------------------------------------------------------

async_test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingAsyncSessionLocal = async_sessionmaker(
    bind=async_test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="function")
async def async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean async database session per test."""
    async with async_test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingAsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

    async with async_test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def async_client(async_db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient with the async DB session overridden."""

    async def override_get_async_db() -> AsyncGenerator[AsyncSession, None]:
        yield async_db_session

    app.dependency_overrides[get_db] = override_get_async_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture()
async def async_test_household(async_db_session: AsyncSession) -> Household:
    """Provide a default household in the async test database."""
    household = Household(name="Test Home")
    async_db_session.add(household)
    await async_db_session.commit()
    await async_db_session.refresh(household)
    return household


@pytest_asyncio.fixture()
async def async_test_user(async_db_session: AsyncSession, async_test_household: Household) -> User:
    """Provide a default user in the async test database."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("password"),
        household_id=async_test_household.id,
    )
    async_db_session.add(user)
    await async_db_session.commit()
    await async_db_session.refresh(user)

    async_test_household.admin_id = user.id
    await async_db_session.commit()
    await async_db_session.refresh(async_test_household)
    return user


@pytest_asyncio.fixture()
async def async_auth_headers(async_test_user: User) -> dict[str, str]:
    """Authorization headers for the default user in async tests."""
    token = create_access_token(subject=str(async_test_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture()
async def async_auth_override(async_test_user: User) -> AsyncGenerator[User, None]:
    """Override get_current_user_async dependency for async routes."""

    async def override():
        return async_test_user

    app.dependency_overrides[get_current_user] = override
    yield async_test_user
    app.dependency_overrides.pop(get_current_user, None)
