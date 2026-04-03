import uuid
from typing import Annotated
from datetime import datetime, timezone

from pydantic import StringConstraints, EmailStr
from sqlalchemy import Column, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Timestamp = datetime


Email = EmailStr


PasswordStr = Annotated[str, StringConstraints(min_length=8, max_length=128)]


Base = declarative_base()


class BaseModel(Base):
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)
