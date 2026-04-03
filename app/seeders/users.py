from .base import SessionLocal, new_uuid
from app.models.users import User
from app.models.households import Household
from app.utils.security import get_password_hash


def seed_users():
    db = SessionLocal()
    try:
        # Create a shared Household for these seed users
        household = Household(name="Test Family")
        db.add(household)
        db.flush()

        users = []
        for i in range(1, 11):
            users.append(
                User(
                    id=new_uuid(),
                    username=f"user{i}",
                    email=f"user{i}@example.com",
                    hashed_password=get_password_hash("password123"),
                    household_id=household.id
                )
            )
        db.add_all(users)
        db.commit()
        print(f"Seeded 10 users into household '{household.name}'")
    except Exception as e:
        db.rollback()
        print("Error seeding users:", e)
    finally:
        db.close()


if __name__ == "__main__":
    seed_users()
