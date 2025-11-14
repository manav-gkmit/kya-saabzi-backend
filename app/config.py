from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):

    APP_NAME: str = "Kya Saabzi App"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    DATABASE_URL: str

    CORS_ORIGINS: list = []

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()  # type: ignore


settings = get_settings()
