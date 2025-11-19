from .base import SessionLocal, new_uuid
from app.models.dishes import Dish


def seed_dishes():
    db = SessionLocal()
    try:
        dish_names = [
            "Aloo Gobhi",
            "Rajma Chawal",
            "Palak Paneer",
            "Bhindi Masala",
            "Chole Bhature",
            "Kadhi Chawal",
            "Baingan Bharta",
            "Matar Paneer",
            "Sambar Rice",
            "Veg Pulao",
        ]
        dishes = [Dish(name=name) for name in dish_names]
        db.add_all(dishes)
        db.commit()
        print("Seeded 10 dishes")
    except Exception as e:
        db.rollback()
        print("Error seeding dishes:", e)
    finally:
        db.close()


if __name__ == "__main__":
    seed_dishes()