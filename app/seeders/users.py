from __future__ import annotations

import asyncio
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import SessionLocal
from app.models.households import Household
from app.models.users import User
from app.utils.security import get_password_hash


async def seed_users(*, db: AsyncSession | None = None) -> None:
    standalone = db is None
    if standalone:
        db = SessionLocal()

    assert db is not None

    try:
        result = await db.execute(select(Household).where(Household.name == "Test Family"))
        household = result.scalars().first()
        if household is None:
            household = Household(name="Test Family")
            db.add(household)
            await db.flush()

        force_password = os.environ.get("SEEDER_FORCE_PASSWORD", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
        }
        seed_password = get_password_hash("password123")
        users: list[User] = []
        for i in range(1, 11):
            email = f"user{i}@example.com"
            username = f"user{i}"
            res = await db.execute(select(User).where(User.email == email))
            user = res.scalars().first()
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
                user.household_id = household.id
                if force_password:
                    user.hashed_password = seed_password
            users.append(user)

        await db.flush()
        if household.admin_id is None and users:
            household.admin_id = users[0].id

        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        if standalone:
            await db.close()


if __name__ == "__main__":
    asyncio.run(seed_users())
