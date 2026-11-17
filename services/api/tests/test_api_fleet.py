"""API integration tests against a seeded disposable database (synthetic fixture data)."""

import json
from collections import defaultdict
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from aerofleet_ml.data.load import UNIT, load_subset
from aerofleet_ml.inference.predictor import RulPredictor
from app.simulation.airline import generate_schedule

from .conftest import SMALL_FLEET, SeededEnv

pytestmark = pytest.mark.db


def _get(client: TestClient, url: str, **params: Any) -> Any:
    response = client.get(url, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_fleet_summary(seeded_client: TestClient) -> None:
    summary = _get(seeded_client, "/api/v1/fleet/summary")
    assert summary["engines"] == summary["aircraft"] == SMALL_FLEET.n_aircraft
    assert summary["flights"] == len(generate_schedule(SMALL_FLEET).flights)
    assert sum(summary["status_counts"].values()) == summary["engines"]
    assert summary["model"]["data_kind"] == "synthetic_fixture"
    assert summary["planning_buffer"] == 10
    assert datetime.fromisoformat(summary["as_of"]) == SMALL_FLEET.start


def test_larger_buffer_never_reduces_flags(seeded_client: TestClient) -> None:
    flagged = []
    for buffer in (0, 10, 40, 120):
        counts = _get(seeded_client, "/api/v1/fleet/summary", buffer=buffer)["status_counts"]
        flagged.append(counts["review"] + counts["critical"])
    assert flagged == sorted(flagged)
    # critical does not depend on the buffer
    crit = {
        _get(seeded_client, "/api/v1/fleet/summary", buffer=b)["status_counts"]["critical"]
        for b in (0, 120)
    }
    assert len(crit) == 1


def test_engine_list_sort_filter_paginate(seeded_client: TestClient) -> None:
    page = _get(seeded_client, "/api/v1/engines")
    margins = [e["planning"]["conservative_margin"] for e in page["items"]]
    assert page["total"] == SMALL_FLEET.n_aircraft and margins == sorted(margins)

    desc = _get(seeded_client, "/api/v1/engines", sort="rul_point", order="desc")["items"]
    points = [e["prediction"]["rul_point"] for e in desc]
    assert points == sorted(points, reverse=True)

    first = _get(seeded_client, "/api/v1/engines", sort="id", page_size=4, page=1)["items"]
    second = _get(seeded_client, "/api/v1/engines", sort="id", page_size=4, page=2)["items"]
    assert [e["id"] for e in first + second] == sorted(e["id"] for e in first + second)
    assert not {e["id"] for e in first} & {e["id"] for e in second}

    for status in ("ok", "review", "critical"):
        items = _get(seeded_client, "/api/v1/engines", status=status, buffer=40)["items"]
        assert all(e["planning"]["status"] == status for e in items)

    one = _get(seeded_client, "/api/v1/engines", aircraft_id="801")
    assert one["total"] == 1 and one["items"][0]["aircraft_id"] == "801"


def test_engine_detail_serves_real_model_predictions(
    seeded_client: TestClient, synthetic_env: SeededEnv
) -> None:
    predictor = RulPredictor.load(synthetic_env.artifact_dir)
    _, test = load_subset(synthetic_env.dataset_dir, "FD001")
    for summary in _get(seeded_client, "/api/v1/engines")["items"]:
        detail = _get(seeded_client, f"/api/v1/engines/{summary['id']}")
        unit = detail["provenance"]["unit_id"]
        history = test[test[UNIT] == unit].drop(columns="rul")
        expected = predictor.predict(history).to_dict()
        assert detail["prediction"] == expected
        assert detail["provenance"]["eval_true_rul"] == int(test[test[UNIT] == unit]["rul"].min())

        flights = detail["flights"]
        assert detail["planning"]["forecast_legs"] == len(flights)
        assert all(f["aircraft_id"] == detail["aircraft_id"] for f in flights)
        flagged = [f["id"] for f in flights if f["flagged"]]
        assert detail["planning"]["first_flagged_flight_id"] == (flagged[0] if flagged else None)
        for f in flights:
            expected_after = round(expected["rul_lower"] - f["cumulative_cycles"], 2)
            assert f["conservative_margin_after"] == pytest.approx(expected_after)
            assert f["flagged"] == (expected_after < detail["planning"]["buffer"])


def test_engine_history_matches_predictor_trajectory(
    seeded_client: TestClient, synthetic_env: SeededEnv
) -> None:
    predictor = RulPredictor.load(synthetic_env.artifact_dir)
    _, test = load_subset(synthetic_env.dataset_dir, "FD001")
    detail = _get(seeded_client, "/api/v1/engines/ENG-801")
    history = _get(
        seeded_client, "/api/v1/engines/ENG-801/history", sensors=["sensor_4", "sensor_11"]
    )
    unit_rows = test[test[UNIT] == detail["provenance"]["unit_id"]]
    trajectory = predictor.predict_trajectory(unit_rows.drop(columns="rul"))

    assert history["cycles"] == unit_rows["cycle"].tolist()
    assert history["cycles"][-1] == detail["observed_cycles"]
    assert [s["name"] for s in history["sensors"]] == ["sensor_4", "sensor_11"]
    assert history["sensors"][0]["values"] == pytest.approx(unit_rows["sensor_4"].tolist())
    assert history["rul_point"] == [p.rul_point for p in trajectory]
    assert history["rul_lower"] == [p.rul_lower for p in trajectory]

    full = _get(seeded_client, "/api/v1/engines/ENG-801/history")
    assert len(full["sensors"]) == 21


def test_flights_filters_and_local_time(seeded_client: TestClient) -> None:
    all_flights = _get(seeded_client, "/api/v1/flights", page_size=500)
    assert all_flights["total"] == len(generate_schedule(SMALL_FLEET).flights)

    by_aircraft: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in all_flights["items"]:
        by_aircraft[f["aircraft_id"]].append(f)
        local = datetime.fromisoformat(f["departure_local"])
        assert local == datetime.fromisoformat(f["departure"])  # same instant
        offset = local.utcoffset()
        assert offset is not None
        if f["origin"] == "PHX":
            assert offset.total_seconds() == -7 * 3600 and f["origin_tz_abbr"] == "MST"
        if f["origin"] == "ORD":
            dst = local.date() >= datetime(2027, 3, 14).date()
            assert f["origin_tz_abbr"] == ("CDT" if dst else "CST")
    for legs in by_aircraft.values():
        assert [f["cumulative_cycles"] for f in legs] == list(range(1, len(legs) + 1))

    phx = _get(seeded_client, "/api/v1/flights", origin="phx", page_size=500)["items"]
    assert phx and all(f["origin"] == "PHX" for f in phx)

    window = _get(
        seeded_client,
        "/api/v1/flights",
        departure_from="2027-03-12T00:00:00Z",
        departure_to="2027-03-13T00:00:00Z",
        page_size=500,
    )["items"]
    assert window and all("2027-03-12" in f["departure"] for f in window)

    flagged = _get(seeded_client, "/api/v1/flights", flagged=True, page_size=500, buffer=40)
    assert all(f["flagged"] for f in flagged["items"])

    by_engine = _get(seeded_client, "/api/v1/flights", engine_id="ENG-802", page_size=500)
    assert by_engine["items"] and all(f["engine_id"] == "ENG-802" for f in by_engine["items"])


def test_seeded_schedule_has_no_overlaps_in_database(seeded_client: TestClient) -> None:
    app = seeded_client.app
    with app.state.session_factory() as session:  # type: ignore[attr-defined]
        overlaps = session.execute(
            text(
                """
                SELECT count(*) FROM flights a JOIN flights b
                  ON a.aircraft_id = b.aircraft_id AND a.id < b.id
                 AND a.scheduled_departure < b.scheduled_arrival
                 AND b.scheduled_departure < a.scheduled_arrival
                """
            )
        ).scalar_one()
        breaks = session.execute(
            text(
                """
                SELECT count(*) FROM (
                  SELECT origin, lag(destination) OVER (
                    PARTITION BY aircraft_id ORDER BY scheduled_departure) AS prev
                  FROM flights) t
                WHERE prev IS NOT NULL AND prev <> origin
                """
            )
        ).scalar_one()
    assert overlaps == 0 and breaks == 0


def test_airports_and_model_metrics(seeded_client: TestClient, synthetic_env: SeededEnv) -> None:
    airports = _get(seeded_client, "/api/v1/airports")
    assert {a["code"] for a in airports} == {a.code for a in SMALL_FLEET.airports}
    metrics = _get(seeded_client, "/api/v1/models/metrics")
    on_disk = json.loads((synthetic_env.artifact_dir / "metrics.json").read_text())
    assert metrics["model"]["version"] == on_disk["model_version"]
    assert metrics["test"]["comparison"] == on_disk["test"]["comparison"]
    assert set(metrics["split"]["fit_units"]).isdisjoint(metrics["split"]["calibration_units"])


@pytest.mark.parametrize(
    ("url", "status", "code"),
    [
        ("/api/v1/engines/ENG-999", 404, "engine_not_found"),
        ("/api/v1/engines/ENG-999/history", 404, "engine_not_found"),
        ("/api/v1/engines/ENG-801/history?sensors=sensor_99", 404, "sensor_not_found"),
        ("/api/v1/engines?sort=bogus", 422, "validation_error"),
        ("/api/v1/engines?page=0", 422, "validation_error"),
        ("/api/v1/engines?status=fine", 422, "validation_error"),
        ("/api/v1/fleet/summary?buffer=-1", 422, "validation_error"),
        ("/api/v1/flights?departure_from=2027-03-12T00:00:00", 422, "naive_datetime"),
        ("/api/v1/flights?origin=CHICAGO", 422, "validation_error"),
    ],
)
def test_errors_use_envelope(seeded_client: TestClient, url: str, status: int, code: str) -> None:
    response = seeded_client.get(url)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_openapi_lists_v1_routes(seeded_client: TestClient) -> None:
    paths = set(seeded_client.get("/openapi.json").json()["paths"])
    assert {
        "/api/v1/fleet/summary",
        "/api/v1/engines",
        "/api/v1/engines/{engine_id}",
        "/api/v1/engines/{engine_id}/history",
        "/api/v1/flights",
        "/api/v1/airports",
        "/api/v1/models/metrics",
    } <= paths
