import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import models
from app.simulation.seed import SeedError, _clear, seed_database

from .conftest import SeededEnv

pytestmark = pytest.mark.db


def test_seed_is_idempotent_and_deterministic(
    seeded_client: TestClient, synthetic_env: SeededEnv
) -> None:
    factory = seeded_client.app.state.session_factory  # type: ignore[attr-defined]
    with factory() as session:
        first = seed_database(
            session,
            synthetic_env.dataset_dir,
            synthetic_env.artifact_dir,
            synthetic_env.config,
            allow_synthetic=True,
        )
        mapping = dict(
            session.execute(select(models.Engine.id, models.Engine.source_unit_id)).all()
        )
        second = seed_database(
            session,
            synthetic_env.dataset_dir,
            synthetic_env.artifact_dir,
            synthetic_env.config,
            allow_synthetic=True,
        )
        assert first == second
        assert (
            dict(session.execute(select(models.Engine.id, models.Engine.source_unit_id)).all())
            == mapping
        )
        assert session.scalar(select(func.count()).select_from(models.Flight)) == second.flights
        assert (
            session.scalar(select(func.count()).select_from(models.EngineObservation))
            == second.observations
        )


def test_seed_refuses_synthetic_model_by_default(
    seeded_client: TestClient, synthetic_env: SeededEnv
) -> None:
    factory = seeded_client.app.state.session_factory  # type: ignore[attr-defined]
    with factory() as session, pytest.raises(SeedError, match="synthetic_fixture"):
        seed_database(
            session, synthetic_env.dataset_dir, synthetic_env.artifact_dir, synthetic_env.config
        )


def test_unseeded_database_returns_actionable_503(seeded_client: TestClient) -> None:
    factory = seeded_client.app.state.session_factory  # type: ignore[attr-defined]
    with factory() as session:
        _clear(session)
        session.commit()
    for url in (
        "/api/v1/fleet/summary",
        "/api/v1/engines",
        "/api/v1/flights",
        "/api/v1/models/metrics",
    ):
        response = seeded_client.get(url)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "not_seeded"
    assert seeded_client.get("/api/v1/airports").json() == []
