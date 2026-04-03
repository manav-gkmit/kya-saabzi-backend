from typing import Optional, Dict, Any, List
from pydantic import BaseModel, UUID4, Field
from app.models.common import Timestamp


class HouseholdBase(BaseModel):
    name: str


class HouseholdCreate(HouseholdBase):
    pass


class HouseholdUpdate(BaseModel):
    name: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None


class HouseholdRead(HouseholdBase):
    id: UUID4
    invite_code: str
    admin_id: Optional[UUID4] = None
    preferences: Optional[Dict[str, Any]] = None
    created_at: Timestamp
    updated_at: Timestamp

    class Config:
        from_attributes = True


class HouseholdJoin(BaseModel):
    invite_code: str = Field(..., min_length=6, max_length=10)
