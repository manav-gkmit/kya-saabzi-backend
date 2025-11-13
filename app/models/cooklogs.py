from sqlalchemy import Column, TIMESTAMP, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from .common import Base


class CookLog(Base):
    __tablename__ = "cooklogs"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    dish_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dishes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        index=True,
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        server_onupdate=text("NOW()"),
    )
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)
