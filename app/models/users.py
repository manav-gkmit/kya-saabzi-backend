from sqlalchemy import String, Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .common import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    email = Column(String(255), nullable=False, unique=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    
    # Connect to a multi-tenant household
    household_id = Column(
        UUID(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    household = relationship("Household", back_populates="users")
