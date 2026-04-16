from pydantic import BaseModel, ConfigDict
from .dishes import DishRead


class ScoreDetail(BaseModel):
    popularity: float
    history: float
    randomness: float
    total: float


class RecommendationRead(BaseModel):
    dish: DishRead
    notes: list[str]
    score_breakdown: ScoreDetail

    model_config = ConfigDict(from_attributes=True)
