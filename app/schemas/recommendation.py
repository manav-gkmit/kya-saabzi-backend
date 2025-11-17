from pydantic import BaseModel
from typing import List
from .dishes import DishRead


class RecommendationRead(BaseModel):
    dish: DishRead
    notes: List[str]

    class Config:
        from_attributes = True
