from pydantic import BaseModel, UUID4
from typing import Optional

from app.models.common import Timestamp


class CookLogBase(BaseModel):
    dish_id: UUID4


class CookLogCreate(CookLogBase):
    pass


class CookLogRead(CookLogBase):
    id: UUID4
    user_id: UUID4
    created_at: Timestamp
    updated_at: Timestamp
    deleted_at: Optional[Timestamp] = None

    class Config:
        orm_mode = True
