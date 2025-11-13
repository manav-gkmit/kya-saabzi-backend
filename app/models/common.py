from typing import Annotated
from datetime import datetime

from pydantic import StringConstraints, EmailStr
from sqlalchemy.ext.declarative import declarative_base

Timestamp = datetime


Email = EmailStr


# Constrained password for create only
PasswordStr = Annotated[str, StringConstraints(min_length=8, max_length=128)]


Base = declarative_base()
