from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from .common import BaseModel


class Dish(BaseModel):
    __tablename__ = "dishes"

    name = Column(String(255), nullable=False, unique=True, index=True)
    cooklogs = relationship("CookLog", back_populates="dish")
