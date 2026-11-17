import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from aerofleet_ml.data.synthetic import write_synthetic_dataset
from aerofleet_ml.pipeline import PipelineConfig, run_pipeline
from app.config import Settings
from app.main import create_app
from app.simulation.airline import ScheduleConfig
from app.simulation.seed import seed_database

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


# --- Seeded database fixtures -------------------------------------------------------------
# Uses the explicitly synthetic C-MAPSS-format fixture and a model trained on it, so tests do
# not need the NASA download. Seeded models are labelled data_kind="synthetic_fixture".

SMALL_FLEET = ScheduleConfig(n_aircraft=10)


@dataclass(frozen=True)
class SeededEnv:
    dataset_dir: Path
    artifact_dir: Path
    config: ScheduleConfig


@pytest.fixture(scope="session")
def synthetic_env(tmp_path_factory: pytest.TempPathFactory) -> SeededEnv:
    dataset_dir = write_synthetic_dataset(tmp_path_factory.mktemp("synthetic"))
    result = run_pipeline(
        dataset_dir,
        tmp_path_factory.mktemp("artifacts"),
        PipelineConfig(cv_folds=3, importance_repeats=1),
    )
    return SeededEnv(dataset_dir, result.artifact_dir, SMALL_FLEET)


def _migrate(url: str) -> None:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


@pytest.fixture(scope="module")
def seeded_client(synthetic_env: SeededEnv) -> Iterator[TestClient]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        if os.environ.get("CI"):
            pytest.fail("TEST_DATABASE_URL must be set in CI")
        pytest.skip("TEST_DATABASE_URL not set")
    _migrate(url)
    settings = Settings(database_url=url, environment="test")
    app = create_app(settings)
    with app.state.session_factory() as session:
        seed_database(
            session,
            synthetic_env.dataset_dir,
            synthetic_env.artifact_dir,
            synthetic_env.config,
            allow_synthetic=True,
        )
    with TestClient(app) as test_client:
        yield test_client
