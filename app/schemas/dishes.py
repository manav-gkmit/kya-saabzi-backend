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
    note: Annotated[
            str, 
            StringConstraints(min_length=3, max_length=255),
        ] = Field(None, examples=["Made it extra spicy"])


class DishRead(DishBase):
    id: UUID4
    created_at: Timestamp
    updated_at: Timestamp
    deleted_at: Optional[Timestamp]

    class Config:
        from_attributes = True
