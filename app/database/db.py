import logging
from collections.abc import AsyncGenerator, Iterator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    future=True,
    echo=settings.DEBUG,
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
    future=True,
)


# --- Asynchronous database configuration ---
# psycopg 3 (psycopg package) natively supports both sync and async via the
# same postgresql+psycopg:// URL scheme, so no driver remapping is required.
async_engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    future=True,
    echo=settings.DEBUG,
)


# expire_on_commit=False on both session factories so that ORM objects remain
# accessible after commit without requiring an explicit refresh in every caller.
# V1 routes that need fresh state call db.refresh() explicitly.
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Iterator[Session]:
    """
    FastAPI dependency that provides a database session.

    Yields:
        Session: The database session.
    """
    db = SessionLocal()
    logger.debug("Database session opened")
    try:
        yield db
    finally:
        db.close()
        logger.debug("Database session closed")


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an asynchronous database session.

    Yields:
        AsyncSession: The async database session.
    """
    async with AsyncSessionLocal() as db:
        logger.debug("Async database session opened")
        try:
            yield db
        finally:
            logger.debug("Async database session closed")

