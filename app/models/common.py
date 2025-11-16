import uuid
from typing import Annotated
from datetime import datetime

from pydantic import StringConstraints, EmailStr
from sqlalchemy import Column, TIMESTAMP, func
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
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)
