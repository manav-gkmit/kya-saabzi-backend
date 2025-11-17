from pydantic import BaseModel, Field, UUID4
from typing import Optional

from app.models.common import Timestamp


class DishBase(BaseModel):
    name: str = Field(..., examples=["Palak Paneer"])
    # Need to think of validation so people dont enter multiple dishes


class DishCreate(DishBase):
    note: Optional[str] = Field(None, examples=["Made it extra spicy"])


class DishRead(DishBase):
    id: UUID4
    created_at: Timestamp
    updated_at: Timestamp
    deleted_at: Optional[Timestamp]

    class Config:
        from_attributes = True
