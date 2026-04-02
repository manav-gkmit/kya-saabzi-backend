import random
from datetime import datetime, timedelta
from .base import SessionLocal, new_uuid
from app.models.users import User
from app.models.cooklogs import CookLog
from app.models.dishes import Dish


def seed_cooklogs():
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.created_at).limit(100).all()
        dishes = db.query(Dish).order_by(Dish.id).limit(100).all()

        if not users or not dishes:
            raise RuntimeError(
                "Ensure users and dishes are seeded before running cooklogs seeder."
            )

        cooklogs = []
        now = datetime.utcnow()
        for i in range(10):
            user = users[i % len(users)]
            dish = dishes[i % len(dishes)]
            cooklogs.append(
                CookLog(
                    id=new_uuid(),
                    user_id=user.id,
                    household_id=user.household_id,
                    dish_id=dish.id,
                    created_at=now - timedelta(days=i * 2),
                    note=f"Test note {i+1}: tried variation {i%3 + 1}",
                    rating=random.randint(1, 5) if i % 2 == 0 else None
                )
            )

        db.add_all(cooklogs)
        db.commit()
        print("Seeded 10 cooklogs")
    except Exception as e:
        db.rollback()
        print("Error seeding cooklogs:", e)
    finally:
        db.close()


if __name__ == "__main__":
    seed_cooklogs()
