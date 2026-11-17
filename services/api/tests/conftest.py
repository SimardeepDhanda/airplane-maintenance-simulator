import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

# A port nothing listens on: used to exercise the "database down" path deterministically.
UNREACHABLE_DB_URL = "postgresql+psycopg://nobody:nothing@127.0.0.1:1/none"


@pytest.fixture
def test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        if os.environ.get("CI"):
            pytest.fail("TEST_DATABASE_URL must be set in CI; database tests may not be skipped")
        pytest.skip("TEST_DATABASE_URL not set; see README > Tests")
    return url


@pytest.fixture
def client(test_database_url: str) -> Iterator[TestClient]:
    settings = Settings(database_url=test_database_url, environment="test")
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def client_without_db() -> Iterator[TestClient]:
    settings = Settings(database_url=UNREACHABLE_DB_URL, environment="test", db_connect_timeout_s=1)
    with TestClient(create_app(settings)) as test_client:
        yield test_client
