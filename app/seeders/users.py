from .base import SessionLocal, pwd_context, new_uuid
from app.models.users import User


def seed_users():
    db = SessionLocal()
    try:
        users = []
        for i in range(1, 11):
            users.append(
                User(
                    id=new_uuid(),
                    username=f"user{i}",
                    email=f"user{i}@example.com",
                    hashed_password=pwd_context.hash("password123"),
                )
            )
        db.add_all(users)
        db.commit()
        print("Seeded 10 users")
    except Exception as e:
        db.rollback()
        print("Error seeding users:", e)
    finally:
        db.close()


if __name__ == "__main__":
    seed_users()
