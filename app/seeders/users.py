from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.models.households import Household
from app.models.users import User
from app.utils.security import get_password_hash


def seed_users(*, db: Session | None = None) -> None:
    standalone = db is None
    if standalone:
        db = SessionLocal()

    assert db is not None

    try:
        household = db.query(Household).filter(Household.name == "Test Family").first()
        if household is None:
            household = Household(name="Test Family")
            db.add(household)
            db.flush()

        seed_password = get_password_hash("password123")
        users: list[User] = []
        for i in range(1, 11):
            email = f"user{i}@example.com"
            username = f"user{i}"
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                user = User(
                    email=email,
                    username=username,
                    hashed_password=seed_password,
                    household_id=household.id,
                )
                db.add(user)
            else:
                user.username = username
                user.hashed_password = seed_password
                user.household_id = household.id
            users.append(user)

        db.flush()
        if household.admin_id is None and users:
            household.admin_id = users[0].id

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        if standalone:
            db.close()


if __name__ == "__main__":
    seed_users()
