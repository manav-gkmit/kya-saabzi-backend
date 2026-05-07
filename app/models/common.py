import uuid
from datetime import UTC, datetime
from typing import Annotated

from pydantic import EmailStr, StringConstraints
from sqlalchemy import TIMESTAMP, Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase

Timestamp = datetime


Email = EmailStr


PasswordStr = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class Base(DeclarativeBase):
    pass


class BaseModel(Base):
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)
