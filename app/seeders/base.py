from uuid import uuid4
from passlib.context import CryptContext
from app.database.db import SessionLocal


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def new_uuid():
    return str(uuid4())
