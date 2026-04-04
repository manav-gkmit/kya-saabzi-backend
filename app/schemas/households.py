from typing import Optional, Dict, Any, List
from pydantic import BaseModel, UUID4, Field, field_validator
from app.models.common import Timestamp


class HouseholdPreferences(BaseModel):
    is_vegetarian: bool = False
    spice_level: str = "medium"
    avoid_ingredients: List[str] = []
    preferred_cuisines: List[str] = []
    recommendation_window_days: int = Field(6, ge=0)
    include_recently_cooked: bool = False


class HouseholdBase(BaseModel):
    name: str


class HouseholdCreate(HouseholdBase):
    pass


class HouseholdUpdate(BaseModel):
    name: Optional[str] = None
    preferences: Optional[HouseholdPreferences] = None


class HouseholdRead(HouseholdBase):
    id: UUID4
    invite_code: str
    admin_id: Optional[UUID4] = None
    preferences: Optional[HouseholdPreferences] = None
    created_at: Timestamp
    updated_at: Timestamp

    class Config:
        from_attributes = True


class HouseholdJoin(BaseModel):
    invite_code: str = Field(..., min_length=6, max_length=10, pattern=r"^[A-Z0-9]+$")

    @field_validator("invite_code", mode="before")
    @classmethod
    def normalize_invite_code(cls, v: Any) -> Any:
        """Strip whitespace and uppercase the invite code before validation."""
        if isinstance(v, str):
            return v.strip().upper()
        return v
