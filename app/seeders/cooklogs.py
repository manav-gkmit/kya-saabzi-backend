from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import SessionLocal
from app.models.cooklogs import CookLog
from app.models.dishes import Dish
from app.models.users import User


async def seed_cooklogs(*, db: AsyncSession | None = None) -> None:
    standalone = db is None
    if standalone:
        db = SessionLocal()

    assert db is not None

    try:
        # Skip if we've already seeded any cooklogs (avoids duplicates on container restart).
        count_res = await db.execute(select(func.count()).select_from(CookLog))
        if (count_res.scalar() or 0) > 0:
            return

        users_res = await db.execute(select(User).order_by(User.created_at).limit(100))
        users = list(users_res.scalars().all())
        
        dishes_res = await db.execute(select(Dish).order_by(Dish.id).limit(100))
        dishes = list(dishes_res.scalars().all())
        
        if not users or not dishes:
            raise RuntimeError("Seed users and dishes before seeding cooklogs.")

        now = datetime.now(UTC)
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
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        if standalone:
            await db.close()


if __name__ == "__main__":
    asyncio.run(seed_cooklogs())
