from sqlalchemy import Column, String, Integer, Enum, Table, ForeignKey
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

    name = Column(String(255), nullable=False, unique=True, index=True)
    
    # Metadata for better recommendation
    dish_type = Column(String(50), nullable=False, default="veg") # veg, non-veg, vegan
    meal_type = Column(String(50), nullable=False, default="lunch") # breakfast, lunch, dinner, snack
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
