from pydantic import UUID4, BaseModel, ConfigDict

from app.models.common import Timestamp

from .dishes import DishBase


class CookLogBase(BaseModel):
    dish_id: UUID4
    note: str | None = None
    rating: int | None = None

    model_config = ConfigDict(from_attributes=True)


class CookLogCreate(CookLogBase):
    pass


class CookLogRead(CookLogBase):
    id: UUID4
    user_id: UUID4
    created_at: Timestamp
    updated_at: Timestamp
    deleted_at: Timestamp | None = None
    dish: DishBase

    model_config = ConfigDict(from_attributes=True)
