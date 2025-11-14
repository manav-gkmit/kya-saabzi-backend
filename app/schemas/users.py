from typing import Optional, Annotated
from app.models.common import PasswordStr, Timestamp, Email

from pydantic import BaseModel, StringConstraints, UUID4


Username = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_.-]+$",
    ),
]


class UserBase(BaseModel):
    email: Email
    username: Username


class UserCreate(UserBase):
    password: PasswordStr


class UserUpdate(BaseModel):
    email: Optional[Email]
    username: Optional[Username]
    password: Optional[PasswordStr]


class UserRead(UserBase):
    id: UUID4
    created_at: Timestamp
    updated_at: Timestamp
    deleted_at: Optional[Timestamp]

    class Config:
        orm_mode = True


class UserInDB(UserBase):
    hashed_password: str
