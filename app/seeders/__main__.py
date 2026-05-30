import asyncio

from app.database.db import SessionLocal

from .cooklogs import seed_cooklogs
from .dishes import seed_dishes
from .users import seed_users


async def main() -> None:
    async with SessionLocal() as db:
        await seed_users(db=db)
        await seed_dishes(db=db)
        await seed_cooklogs(db=db)


if __name__ == "__main__":
    asyncio.run(main())
