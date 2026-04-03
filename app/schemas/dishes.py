from pydantic import BaseModel, Field, UUID4, field_validator, StringConstraints
from typing import Optional, Annotated

from app.models.common import Timestamp


class DishBase(BaseModel):
    name: str = Field(..., examples=["Palak Paneer"])

    @field_validator('name')
    def check_dish(cls, v: str):
        stripped_v = v.strip()
        if not stripped_v:
            raise ValueError("Dish name cannot be empty")
        
        if not all(c.isalpha() or c.isspace() for c in stripped_v):
            raise ValueError("Dish can only contain alphabets and spaces")
        
        if '  ' in stripped_v:
            raise ValueError(
                "Dish name cannot contain multiple consecutive spaces"
            )
            
        return stripped_v


class DishCreate(DishBase):
    note: Optional[Annotated[
            str, 
            StringConstraints(min_length=3, max_length=255),
        ]] = Field(None, examples=["Made it extra spicy"])
    rating: Optional[int] = Field(None, ge=1, le=5, examples=[4])
    spiciness: int = Field(1, ge=1, le=5, examples=[2])
    meal_type: Optional[str] = Field(None, examples=["lunch"]) # 'breakfast', 'lunch', 'dinner', 'snack'
    dish_type: str = Field("veg", examples=["veg"]) # 'veg', 'non-veg', 'vegan'
    prep_time_minutes: Optional[int] = Field(None, examples=[30])
    calories_estimate: Optional[int] = Field(None, examples=[350])


class DishSearchResponse(BaseModel):
    id: UUID4
    name: str
    similarity: float


class DishRead(DishBase):
    id: UUID4
    dish_type: str
    meal_type: str
    spiciness: int
    prep_time_minutes: Optional[int] = None
    calories_estimate: Optional[int] = None
    created_at: Timestamp
    updated_at: Timestamp
    deleted_at: Optional[Timestamp]

    class Config:
        from_attributes = True
