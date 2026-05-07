from typing import Annotated

from pydantic import UUID4, BaseModel, ConfigDict, EmailStr, StringConstraints

from app.models.common import Email, PasswordStr, Timestamp

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
    household_name: str | None = None  # If code is not provided, creates a new one
    invite_code: str | None = None  # Use this to join existing instead of creating


class UserUpdate(BaseModel):
    email: Email | None = None
    username: Username | None = None
    password: PasswordStr | None = None


class UserRead(BaseModel):
    id: UUID4
    email: Email
    username: Username
    household_id: UUID4 | None = None
    created_at: Timestamp
    updated_at: Timestamp
    deleted_at: Timestamp | None = None

    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserBase):
    hashed_password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: PasswordStr
