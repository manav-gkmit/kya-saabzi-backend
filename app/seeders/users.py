from .base import SessionLocal, pwd_context, new_uuid
from app.models.users import User
from app.models.households import Household


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
                    hashed_password=pwd_context.hash("password123"),
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
