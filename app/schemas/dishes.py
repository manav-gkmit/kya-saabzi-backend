from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import UUID4, BaseModel, ConfigDict, Field, StringConstraints, field_validator


class DishBase(BaseModel):
    name: str = Field(..., examples=["Palak Paneer"])

    @field_validator("name")
    @classmethod
    def check_dish(cls, v: str) -> str:
        stripped_v = v.strip()
        if not stripped_v:
            raise ValueError("Dish name cannot be empty")

        if not all(c.isalpha() or c.isspace() for c in stripped_v):
            raise ValueError("Dish can only contain alphabets and spaces")

        if "  " in stripped_v:
            raise ValueError("Dish name cannot contain multiple consecutive spaces")

        return stripped_v


class DishCreate(DishBase):
    note: (
        Annotated[
            str,
            StringConstraints(min_length=3, max_length=255),
        ]
        | None
    ) = Field(None, examples=["Made it extra spicy"])
    rating: int | None = Field(None, ge=1, le=5, examples=[4])
    spiciness: int = Field(1, ge=1, le=5, examples=[2])
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"] | None = Field(
        None, examples=["lunch"]
    )
    dish_type: Literal["veg", "non-veg", "vegan"] = Field("veg", examples=["veg"])
    prep_time_minutes: int | None = Field(None, examples=[30])
    calories_estimate: int | None = Field(None, examples=[350])
    ingredients: list[str] | None = Field(None, examples=[["spinach", "paneer", "garlic"]])

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, v: object) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v  # let pydantic raise a type error


class DishSearchResponse(BaseModel):
    id: UUID4
    name: str
    similarity: float

    model_config = ConfigDict(from_attributes=True)


class DishRead(DishBase):
    id: UUID4
    dish_type: str
    meal_type: str
    spiciness: int
    prep_time_minutes: int | None = None
    calories_estimate: int | None = None
    ingredients: list[str] = []
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)

    @field_validator("ingredients", mode="before")
    @classmethod
    def extract_ingredient_names(cls, v: object) -> list[str]:
        if not v:
            return []
        return [ing.name if hasattr(ing, "name") else str(ing) for ing in v]
