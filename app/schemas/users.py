from datetime import datetime
from typing import Annotated

from pydantic import UUID4, BaseModel, ConfigDict, EmailStr, StringConstraints

PasswordStr = Annotated[
    str,
    StringConstraints(min_length=8, max_length=128),
]

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
    email: EmailStr
    username: Username


class UserCreate(UserBase):
    password: PasswordStr
    household_name: str | None = None  # If code is not provided, creates a new one
    invite_code: str | None = None  # Use this to join existing instead of creating


class UserRead(BaseModel):
    id: UUID4
    email: EmailStr
    username: Username
    household_id: UUID4 | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    email: EmailStr
    password: PasswordStr
