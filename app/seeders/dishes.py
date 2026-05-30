from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import SessionLocal
from app.models.dishes import Dish, Ingredient


async def seed_dishes(*, db: AsyncSession | None = None) -> None:
    standalone = db is None
    if standalone:
        db = SessionLocal()

    assert db is not None

    try:
        ingredients_list: list[dict[str, str | None]] = [
            {"name": "Paneer", "category": "Protein"},
            {"name": "Potato", "category": "Vegetable"},
            {"name": "Cauliflower", "category": "Vegetable"},
            {"name": "Chicken", "category": "Protein"},
            {"name": "Spinach", "category": "Vegetable"},
            {"name": "Lentils (Dal)", "category": "Protein"},
            {"name": "Rice", "category": "Grain"},
            {"name": "Wheat Flour", "category": "Grain"},
            {"name": "Tomato", "category": "Vegetable"},
            {"name": "Onion", "category": "Vegetable"},
            {"name": "Ginger-Garlic Paste", "category": "Spice"},
        ]
        db_ingredients: dict[str, Ingredient] = {}
        for ing_data in ingredients_list:
            name = str(ing_data["name"])
            res = await db.execute(select(Ingredient).where(Ingredient.name == name))
            ing = res.scalars().first()
            if ing is None:
                ing = Ingredient(**ing_data)
                db.add(ing)
            db_ingredients[name] = ing

        dishes_list: list[dict[str, object]] = [
            {
                "name": "Paneer Butter Masala",
                "dish_type": "veg",
                "meal_type": "lunch",
                "spiciness": 2,
                "prep_time_minutes": 30,
                "calories_estimate": 450,
                "ingredients": ["Paneer", "Tomato", "Onion", "Ginger-Garlic Paste"],
            },
            {
                "name": "Aloo Gobi",
                "dish_type": "veg",
                "meal_type": "lunch",
                "spiciness": 3,
                "prep_time_minutes": 25,
                "calories_estimate": 250,
                "ingredients": ["Potato", "Cauliflower", "Onion"],
            },
            {
                "name": "Dal Tadka",
                "dish_type": "veg",
                "meal_type": "dinner",
                "spiciness": 2,
                "prep_time_minutes": 20,
                "calories_estimate": 200,
                "ingredients": ["Lentils (Dal)", "Tomato", "Onion"],
            },
            {
                "name": "Chicken Curry",
                "dish_type": "non-veg",
                "meal_type": "dinner",
                "spiciness": 4,
                "prep_time_minutes": 45,
                "calories_estimate": 550,
                "ingredients": ["Chicken", "Tomato", "Onion", "Ginger-Garlic Paste"],
            },
            {
                "name": "Palak Paneer",
                "dish_type": "veg",
                "meal_type": "dinner",
                "spiciness": 2,
                "prep_time_minutes": 30,
                "calories_estimate": 350,
                "ingredients": ["Paneer", "Spinach", "Onion"],
            },
            {
                "name": "Paratha",
                "dish_type": "veg",
                "meal_type": "breakfast",
                "spiciness": 1,
                "prep_time_minutes": 15,
                "calories_estimate": 300,
                "ingredients": ["Wheat Flour", "Potato"],
            },
        ]

        for d_data in dishes_list:
            ingredient_names = list(d_data.pop("ingredients"))
            name = str(d_data["name"])
            res = await db.execute(select(Dish).where(Dish.name == name))
            dish = res.scalars().first()
            if dish is None:
                dish = Dish(**d_data)
                db.add(dish)
            else:
                for key, value in d_data.items():
                    setattr(dish, key, value)

            # Use sync append since ingredients is loaded/managed here
            dish.ingredients = [db_ingredients[str(n)] for n in ingredient_names]

        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        if standalone:
            await db.close()


if __name__ == "__main__":
    asyncio.run(seed_dishes())
