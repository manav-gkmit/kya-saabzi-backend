from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from .common import BaseModel


class CookLog(BaseModel):
    __tablename__ = "cooklogs"

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
