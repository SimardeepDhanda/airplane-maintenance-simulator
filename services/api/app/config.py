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
    # Optional, for hosts that give each deployment its own address (e.g. Vercel previews).
    cors_origin_regex: str | None = None
    environment: Literal["development", "test", "production"] = "development"
    db_connect_timeout_s: int = Field(default=3, ge=1, le=30)
    planning_buffer_cycles: int = Field(default=10, ge=0, le=200)

    @field_validator("database_url")
    @classmethod
    def _check_scheme(cls, value: str) -> str:
        # Hosts such as Neon hand out plain postgres URLs; use the psycopg 3 driver for them.
        for plain in ("postgresql://", "postgres://"):
            if value.startswith(plain):
                value = "postgresql+psycopg://" + value.removeprefix(plain)
        if not value.startswith(_ALLOWED_DB_SCHEMES):
            raise ValueError(f"DATABASE_URL must start with one of {_ALLOWED_DB_SCHEMES}")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        # Origins never carry a path; tolerate "https://site.app/" or "https://site.app/overview".
        if isinstance(value, str):
            value = value.split(",")
        if isinstance(value, list):
            return [_origin(str(v)) for v in value if str(v).strip()]
        return value


def _origin(value: str) -> str:
    value = value.strip()
    scheme, sep, rest = value.partition("://")
    return f"{scheme}{sep}{rest.split('/', 1)[0]}" if sep else value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # values come from the environment
