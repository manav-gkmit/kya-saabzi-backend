from uuid import uuid4
from app.database.db import SessionLocal


def new_uuid():
    return str(uuid4())
