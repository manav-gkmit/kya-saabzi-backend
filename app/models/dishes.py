from sqlalchemy import Column, String, Integer, Enum, Table, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .common import BaseModel, Base

# Association table for Dish <-> Ingredient
dish_ingredients = Table(
    "dish_ingredients",
    Base.metadata,
    Column("dish_id", ForeignKey("dishes.id", ondelete="CASCADE"), primary_key=True),
    Column("ingredient_id", ForeignKey("ingredients.id", ondelete="CASCADE"), primary_key=True),
)


class Dish(BaseModel):
    __tablename__ = "dishes"
    __table_args__ = (CheckConstraint("spiciness >= 1 AND spiciness <= 5", name="check_spiciness_range"),)

    household_id = Column(
        UUID(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    name = Column(String(255), nullable=False, index=True)
    
    # Metadata for better recommendation
    dish_type = Column(
        String(50), 
        CheckConstraint("dish_type IN ('veg', 'non-veg', 'vegan')", name="check_dish_type"),
        nullable=False, 
        default="veg"
    )
    meal_type = Column(
        String(50), 
        CheckConstraint("meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')", name="check_meal_type"),
        nullable=False, 
        default="lunch"
    )
    spiciness = Column(Integer, nullable=False, default=1) # 1–5
    prep_time_minutes = Column(Integer, nullable=True) # in minutes
    calories_estimate = Column(Integer, nullable=True)

    cooklogs = relationship("CookLog", back_populates="dish")
    ingredients = relationship("Ingredient", secondary=dish_ingredients, back_populates="dishes")


class Ingredient(BaseModel):
    __tablename__ = "ingredients"

    name = Column(String(255), nullable=False, unique=True, index=True)
    category = Column(String(100), nullable=True) # vegetable, spice, protein, etc.

    dishes = relationship("Dish", secondary=dish_ingredients, back_populates="ingredients")
