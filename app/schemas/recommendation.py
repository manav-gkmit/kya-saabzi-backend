from pydantic import BaseModel
from typing import List
from .dishes import DishRead


class ScoreDetail(BaseModel):
    popularity: float
    history: float
    randomness: float
    total: float


class RecommendationRead(BaseModel):
    dish: DishRead
    notes: List[str]
    score_breakdown: ScoreDetail

    class Config:
        from_attributes = True
