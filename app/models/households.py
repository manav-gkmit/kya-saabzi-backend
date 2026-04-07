from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from .common import BaseModel
import secrets
import string


def generate_invite_code():
    return "".join(
        secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8)
    )


class Household(BaseModel):
    __tablename__ = "households"

    name = Column(String(255), nullable=False)
    invite_code = Column(
        String(10), unique=True, nullable=False, index=True, default=generate_invite_code
    )
    admin_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    preferences = Column(
        JSONB,
        nullable=True,
        default=lambda: {
            "is_vegetarian": False,
            "spice_level": "medium",
            "avoid_ingredients": [],
            "preferred_cuisines": [],
            "recommendation_window_days": 6,
            "include_recently_cooked": False,
        },
    )

    users = relationship(
        "User", back_populates="household", foreign_keys="User.household_id"
    )
    admin = relationship("User", foreign_keys="Household.admin_id")
    cooklogs = relationship("CookLog", back_populates="household")
