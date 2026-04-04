from pydantic import BaseModel
from .users import UserRead


class Token(BaseModel):
    access_token: str
    user: UserRead
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str | None = None
    exp: int | None = None
    jti: str | None = None
