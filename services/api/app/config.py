"""Environment-driven configuration. Invalid settings fail at startup, not at first request."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_ALLOWED_DB_SCHEMES = ("postgresql+psycopg://",)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        description="SQLAlchemy URL, e.g. postgresql+psycopg://user:pw@host/db"
    )
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    environment: Literal["development", "test", "production"] = "development"
    db_connect_timeout_s: int = Field(default=3, ge=1, le=30)

    @field_validator("database_url")
    @classmethod
    def _check_scheme(cls, value: str) -> str:
        if not value.startswith(_ALLOWED_DB_SCHEMES):
            raise ValueError(f"DATABASE_URL must start with one of {_ALLOWED_DB_SCHEMES}")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # values come from the environment
