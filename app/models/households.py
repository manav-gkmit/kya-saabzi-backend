from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from .common import BaseModel


class Household(BaseModel):
    __tablename__ = "households"

    name = Column(String(255), nullable=False)
    preferences = Column(
        JSONB,
        nullable=True,
        default=lambda: {
            "is_vegetarian": False,
            "spice_level": "medium",
            "avoid_ingredients": [],
            "preferred_cuisines": [],
        },
    )

    users = relationship("User", back_populates="household")
    cooklogs = relationship("CookLog", back_populates="household")
