from sqlalchemy import Column, ForeignKey, String, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .common import BaseModel


class CookLog(BaseModel):
    __tablename__ = "cooklogs"

    household_id = Column(
        UUID(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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
    
    note = Column(String, nullable=True)
    rating = Column(Integer, nullable=True) # 1-5 rating for personalized reco weighting

    dish = relationship("Dish", back_populates="cooklogs")
    household = relationship("Household", back_populates="cooklogs")
