import pytest
from pydantic import ValidationError

from app.config import Settings

VALID_URL = "postgresql+psycopg://u:p@localhost:5432/db"


def test_rejects_non_postgres_url() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(database_url="sqlite:///local.db")


def test_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_rejects_unknown_environment() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=VALID_URL, environment="staging")


def test_parses_comma_separated_cors_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", VALID_URL)
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, https://example.test ,")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["http://localhost:3000", "https://example.test"]
