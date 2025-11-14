from pydantic import BaseModel, Field, UUID4
from typing import Optional

from app.models.common import Timestamp


class DishBase(BaseModel):
    name: str = Field(..., examples=["Palak Paneer, Aloo Gobi"])


class DishCreate(DishBase):
    pass


class DishRead(DishBase):
    id: UUID4
    created_at: Timestamp
    updated_at: Timestamp
    deleted_at: Optional[Timestamp]

    class Config:
        orm_mode = True
