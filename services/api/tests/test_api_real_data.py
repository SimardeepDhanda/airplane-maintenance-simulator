"""Seeds the real NASA-derived fleet into the test database and checks that the API serves the
trained model's predictions. Needs `make data` and `make pipeline`; run with `pytest -m dataset`."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aerofleet_ml.data.load import UNIT, load_subset
from aerofleet_ml.inference.predictor import RulPredictor
from app.config import Settings
from app.main import create_app
from app.simulation.seed import seed_database

from .conftest import _migrate

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data" / "raw" / "cmapss"
ARTIFACTS = REPO_ROOT / "ml" / "artifacts"

pytestmark = [pytest.mark.dataset, pytest.mark.db]


@pytest.fixture(scope="module")
def real_client() -> Iterator[tuple[TestClient, Path]]:
    url = os.environ.get("TEST_DATABASE_URL")
    artifact_dir = ARTIFACTS / (ARTIFACTS / "LATEST").read_text().strip()
    if not url or not (artifact_dir / "model.joblib").is_file() or not DATA_DIR.is_dir():
        pytest.fail("needs TEST_DATABASE_URL, `make data` and `make pipeline`")
    _migrate(url)
    app = create_app(Settings(database_url=url, environment="test"))
    with app.state.session_factory() as session:
        seed_database(session, DATA_DIR, artifact_dir)
    with TestClient(app) as client:
        yield client, artifact_dir


def test_api_serves_trained_model_predictions_for_nasa_engines(
    real_client: tuple[TestClient, Path],
) -> None:
    client, artifact_dir = real_client
    predictor = RulPredictor.load(artifact_dir)
    _, test = load_subset(DATA_DIR, "FD001")

    summary = client.get("/api/v1/fleet/summary").json()
    assert summary["model"] == {
        "version": predictor.model_version,
        "data_kind": "nasa_cmapss",
        "subset": "FD001",
        "trained_at": summary["model"]["trained_at"],
    }
    engines = client.get("/api/v1/engines").json()["items"]
    assert len(engines) == 20
    units = set()
    for engine in engines:
        detail = client.get(f"/api/v1/engines/{engine['id']}").json()
        unit = detail["provenance"]["unit_id"]
        units.add(unit)
        history = test[test[UNIT] == unit].drop(columns="rul")
        assert detail["prediction"] == predictor.predict(history).to_dict()
        assert detail["provenance"]["dataset"] == "NASA C-MAPSS"
        assert detail["provenance"]["split"] == "test"
    assert len(units) == 20  # each NASA engine used once


def _scenario(client: TestClient, assumptions: dict[str, object]) -> dict[str, object]:
    sid = client.post("/api/v1/scenarios", json={"assumptions": assumptions}).json()["id"]
    assert client.post(f"/api/v1/scenarios/{sid}/solve").status_code == 202
    result: dict[str, object] = client.get(f"/api/v1/scenarios/{sid}").json()
    return result


def test_planner_on_real_fleet(real_client: tuple[TestClient, Path]) -> None:
    """Default week: every job placed and verified, optimizer no worse than the baseline.
    The documented infeasible demo (hard threshold, one DEN bay out) names the two DEN jobs."""
    client, _ = real_client
    s = _scenario(client, {})
    base, opt = s["baseline"], s["optimized"]
    assert isinstance(base, dict) and isinstance(opt, dict)
    assert opt["status"] == "OPTIMAL" and opt["verified"] and base["verified"]
    assert opt["objective"] <= base["objective"]
    assert len(opt["placements"]) == len(opt["jobs"]) > 0

    hard = _scenario(client, {"threshold_policy": "hard", "bay_changes": {"DEN": -1}})
    opt = hard["optimized"]
    assert isinstance(opt, dict) and opt["status"] == "INFEASIBLE"
    (explanation,) = opt["explanations"]
    assert explanation["code"] == "resource_conflict"
    assert "ENG-802" in explanation["message"] and "ENG-808" in explanation["message"]
