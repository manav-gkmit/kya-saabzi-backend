import uuid
from sqlalchemy.orm import Session
from app.models.dishes import Dish, Ingredient


def seed_dishes(db: Session):
    # 1. Create Ingredients
    ingredients_list = [
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
    
    db_ingredients = {}
    for ing_data in ingredients_list:
        ing = db.query(Ingredient).filter(Ingredient.name == ing_data["name"]).first()
        if not ing:
            ing = Ingredient(**ing_data)
            db.add(ing)
        db_ingredients[ing_data["name"]] = ing
    
    db.commit()

    # 2. Create Dishes
    dishes_list = [
        {
            "name": "Paneer Butter Masala",
            "dish_type": "veg",
            "meal_type": "lunch",
            "spiciness": 2,
            "prep_time_minutes": 30,
            "calories_estimate": 450,
            "ingredients": ["Paneer", "Tomato", "Onion", "Ginger-Garlic Paste"]
        },
        {
            "name": "Aloo Gobi",
            "dish_type": "veg",
            "meal_type": "lunch",
            "spiciness": 3,
            "prep_time_minutes": 25,
            "calories_estimate": 250,
            "ingredients": ["Potato", "Cauliflower", "Onion"]
        },
        {
            "name": "Dal Tadka",
            "dish_type": "veg",
            "meal_type": "dinner",
            "spiciness": 2,
            "prep_time_minutes": 20,
            "calories_estimate": 200,
            "ingredients": ["Lentils (Dal)", "Tomato", "Onion"]
        },
        {
            "name": "Chicken Curry",
            "dish_type": "non-veg",
            "meal_type": "dinner",
            "spiciness": 4,
            "prep_time_minutes": 45,
            "calories_estimate": 550,
            "ingredients": ["Chicken", "Tomato", "Onion", "Ginger-Garlic Paste"]
        },
        {
            "name": "Palak Paneer",
            "dish_type": "veg",
            "meal_type": "dinner",
            "spiciness": 2,
            "prep_time_minutes": 30,
            "calories_estimate": 350,
            "ingredients": ["Paneer", "Spinach", "Onion"]
        },
        {
            "name": "Paratha",
            "dish_type": "veg",
            "meal_type": "breakfast",
            "spiciness": 1,
            "prep_time_minutes": 15,
            "calories_estimate": 300,
            "ingredients": ["Wheat Flour", "Potato"]
        }
    ]

    for d_data in dishes_list:
        dish = db.query(Dish).filter(Dish.name == d_data["name"]).first()
        if not dish:
            ingredient_names = d_data.pop("ingredients")
            dish = Dish(**d_data)
            for name in ingredient_names:
                dish.ingredients.append(db_ingredients[name])
            db.add(dish)
    
    db.commit()