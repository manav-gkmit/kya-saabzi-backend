from sqlalchemy import String, Column
from .common import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    email = Column(String(255), nullable=False, unique=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
