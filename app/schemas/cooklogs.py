from datetime import datetime

from pydantic import UUID4, BaseModel, ConfigDict

from .dishes import DishBase


class CookLogBase(BaseModel):
    dish_id: UUID4
    note: str | None = None
    rating: int | None = None

    model_config = ConfigDict(from_attributes=True)


class CookLogRead(CookLogBase):
    id: UUID4
    user_id: UUID4
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    dish: DishBase

    model_config = ConfigDict(from_attributes=True)
