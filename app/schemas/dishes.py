from pydantic import BaseModel, Field
from typing import Optional

from models.common import Timestamp


class DishBase(BaseModel):
    name: str = Field(..., examples=["Palak Paneer, Aloo Gobi"])


class DishCreate(DishBase):
    pass


class DishRead(DishBase):
    id: int
    created_at: Timestamp
    updated_at: Timestamp
    deleted_at: Optional[Timestamp]

    class Config:
        orm_mode = True
