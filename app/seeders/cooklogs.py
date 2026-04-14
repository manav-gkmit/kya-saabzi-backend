from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.models.cooklogs import CookLog
from app.models.dishes import Dish
from app.models.users import User


def seed_cooklogs(*, db: Session | None = None) -> None:
    standalone = db is None
    if standalone:
        db = SessionLocal()

    assert db is not None

    try:
        # Skip if we've already seeded any cooklogs (avoids duplicates on container restart).
        if db.query(CookLog).count() > 0:
            return

        users = db.query(User).order_by(User.created_at).limit(100).all()
        dishes = db.query(Dish).order_by(Dish.id).limit(100).all()
        if not users or not dishes:
            raise RuntimeError("Seed users and dishes before seeding cooklogs.")

        now = datetime.now(timezone.utc)
        cooklogs: list[CookLog] = []
        for i in range(10):
            user = users[i % len(users)]
            dish = dishes[i % len(dishes)]
            cooklogs.append(
                CookLog(
                    user_id=user.id,
                    household_id=user.household_id,
                    dish_id=dish.id,
                    created_at=now - timedelta(days=i * 2),
                    note=f"Seeded: variation {i % 3 + 1}",
                    rating=random.randint(1, 5) if i % 2 == 0 else None,
                )
            )

        db.add_all(cooklogs)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        if standalone:
            db.close()


if __name__ == "__main__":
    seed_cooklogs()
