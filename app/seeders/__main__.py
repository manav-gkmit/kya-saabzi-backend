from __future__ import annotations

from app.database.db import SessionLocal

from .cooklogs import seed_cooklogs
from .dishes import seed_dishes
from .users import seed_users


def main() -> None:
    db = SessionLocal()
    try:
        seed_users(db=db)
        seed_dishes(db=db)
        seed_cooklogs(db=db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
