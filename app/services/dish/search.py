import difflib
from uuid import UUID

from sqlalchemy.orm import Session

from app.database.helpers import escape_like
from app.models.dishes import Dish

# Upper bound on candidate rows fetched from DB before Python-level similarity scoring.
# Keeps memory usage O(1) regardless of table size.
_SEARCH_CANDIDATE_LIMIT = 100


def search_dishes(
    db: Session,
    query: str,
    *,
    household_id: UUID,
    limit: int = 5,
    offset: int = 0,
) -> list[dict]:
    q_escaped = escape_like(query)
    rows = (
        db.query(Dish.id, Dish.name)
        .filter(Dish.name.ilike(f"%{q_escaped}%", escape="\\"))
        .filter((Dish.household_id == household_id) | (Dish.household_id.is_(None)))
        .limit(_SEARCH_CANDIDATE_LIMIT)
        .all()
    )

    q_lower = query.lower()
    scored: list[dict] = [
        {
            "id": dish_id,
            "name": dish_name,
            "similarity": difflib.SequenceMatcher(None, q_lower, dish_name.lower()).ratio(),
        }
        for dish_id, dish_name in rows
    ]

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[offset : offset + limit]
