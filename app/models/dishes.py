from sqlalchemy import Column, String
from .common import BaseModel


class Dish(BaseModel):
    __tablename__ = "dishes"

    name = Column(String(255), nullable=False, unique=True, index=True)
