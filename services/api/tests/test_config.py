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


@pytest.mark.parametrize("scheme", ["postgresql://", "postgres://"])
def test_plain_postgres_urls_use_psycopg(scheme: str) -> None:
    url = f"{scheme}u:p@ep-x.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    settings = Settings(database_url=url)
    assert settings.database_url == (
        "postgresql+psycopg://u:p@ep-x.us-east-2.aws.neon.tech/neondb"
        "?sslmode=require&channel_binding=require"
    )


def test_cors_origins_drop_paths_and_trailing_slashes() -> None:
    settings = Settings(
        database_url=VALID_URL,
        cors_origins="https://a.vercel.app/overview, https://b.vercel.app/,http://localhost:3000",
    )
    assert settings.cors_origins == [
        "https://a.vercel.app",
        "https://b.vercel.app",
        "http://localhost:3000",
    ]


def test_cors_origin_regex_allows_preview_deployments() -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    settings = Settings(
        database_url="postgresql+psycopg://u:p@127.0.0.1:1/none",
        db_connect_timeout_s=1,
        cors_origins="https://site.vercel.app",
        cors_origin_regex=r"https://site(-[a-z0-9-]+)?\.vercel\.app",
    )
    with TestClient(create_app(settings)) as client:
        for origin, allowed in [
            ("https://site.vercel.app", True),
            ("https://site-2b7kd2itm-team.vercel.app", True),
            ("https://evil.vercel.app", False),
        ]:
            r = client.get("/health", headers={"Origin": origin})
            assert (r.headers.get("access-control-allow-origin") == origin) is allowed, origin
