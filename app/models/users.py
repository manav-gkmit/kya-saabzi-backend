from sqlalchemy import String, Column, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID

from .common import Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    email = Column(String(255), nullable=False, unique=True)
    username = Column(String(50), nullable=False, unique=True, index=True)

    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )

    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        server_onupdate=text("NOW()"),
    )

    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)
