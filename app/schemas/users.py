from typing import Optional, Annotated
from app.models.common import PasswordStr, Timestamp, Email

from pydantic import BaseModel, StringConstraints, UUID4, EmailStr


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
    household_name: Optional[str] = None # If provided, creates a new household


class UserUpdate(BaseModel):
    email: Optional[Email]
    username: Optional[Username]
    password: Optional[PasswordStr]


class UserRead(BaseModel):
    id: UUID4
    email: Email
    username: Username
    household_id: Optional[UUID4] = None
    created_at: Timestamp
    updated_at: Timestamp
    deleted_at: Optional[Timestamp]

    class Config:
        from_attributes = True


class UserInDB(UserBase):
    hashed_password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: PasswordStr
