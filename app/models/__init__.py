# Comes handy for future alembic migrations
from .common import Base

from . import users, dishes, cooklogs


__all__ = ["Base", "users", "dishes", "cooklogs"]
