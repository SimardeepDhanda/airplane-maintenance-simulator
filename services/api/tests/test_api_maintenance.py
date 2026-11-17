"""Maintenance resources, baseline plan and scenario lifecycle against the seeded test database."""

from __future__ import annotations

from datetime import datetime, timedelta
from itertools import pairwise
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.services import maintenance as maintenance_service
from app.services.fleet import load_snapshot

pytestmark = pytest.mark.db

WIDE = 60  # buffer that flags several engines in the small synthetic fleet


def _get(client: TestClient, path: str, **params: Any) -> Any:
    r = client.get(path, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _run(client: TestClient, assumptions: dict[str, Any], name: str | None = None) -> Any:
    body: dict[str, Any] = {"assumptions": assumptions}
    if name:
        body["name"] = name
    created = client.post("/api/v1/scenarios", json=body)
    assert created.status_code == 201, created.text
    sid = created.json()["id"]
    assert created.json()["status"] == "created"
    queued = client.post(f"/api/v1/scenarios/{sid}/solve")
    assert queued.status_code == 202, queued.text
    # TestClient runs background tasks before returning, so the result is ready.
    return _get(client, f"/api/v1/scenarios/{sid}")


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _check_plan_against_schedule(
    client: TestClient, plan: dict[str, Any], grounded: tuple[str, ...] = ()
) -> None:
    """Independent of the optimizer: maintenance never overlaps a kept flight, and the aircraft
    is at the facility when work starts."""
    flights = _get(client, "/api/v1/flights", page_size=1000)["items"]
    resources = _get(client, "/api/v1/maintenance/resources")
    bays = {f["code"]: len(f["bays"]) for f in resources["facilities"]}
    by_ship: dict[str, list[dict[str, Any]]] = {}
    for f in flights:
        by_ship.setdefault(f["aircraft_id"], []).append(f)
    initial = {a: fl[0]["origin"] for a, fl in by_ship.items()}
    for p in plan["placements"]:
        start, end = _ts(p["start"]), _ts(p["end"])
        cancelled = set(p["cancelled_flights"])
        kept = (
            []
            if p["aircraft_id"] in grounded
            else [f for f in by_ship.get(p["aircraft_id"], []) if f["id"] not in cancelled]
        )
        location = initial.get(p["aircraft_id"], p["facility"])
        for f in kept:
            assert not (_ts(f["departure"]) < end and _ts(f["arrival"]) > start), (p, f)
            if _ts(f["arrival"]) <= start:
                location = f["destination"]
        assert location == p["facility"], p
        assert p["bay"].startswith(p["facility"])
        assert p["facility"] in bays
    # Bays are never double-booked.
    by_bay: dict[str, list[tuple[datetime, datetime]]] = {}
    for p in plan["placements"]:
        by_bay.setdefault(p["bay"], []).append((_ts(p["start"]), _ts(p["end"])))
    for intervals in by_bay.values():
        intervals.sort()
        for (_, e1), (s2, _) in pairwise(intervals):
            assert e1 <= s2


def test_resources(seeded_client: TestClient) -> None:
    r = _get(seeded_client, "/api/v1/maintenance/resources")
    facilities = {f["code"]: f for f in r["facilities"]}
    assert set(facilities) == {"ATL", "DEN", "ORD"}
    assert facilities["ATL"]["supports"] == ["borescope"]
    assert "engine_change" in facilities["ORD"]["supports"]
    assert [b["id"] for b in facilities["ORD"]["bays"]] == ["ORD-1", "ORD-2"]
    assert {s["name"] for s in facilities["DEN"]["shifts"]} == {"day", "night"}
    assert {p["id"] for p in r["parts"]} == {"SE-ORD", "SE-DEN", "SE-DEN-INBOUND"}
    assert {j["id"] for j in r["job_types"]} == {"engine_change", "borescope"}
    assert _ts(r["horizon_end"]) - _ts(r["horizon_start"]) == timedelta(days=7)


def test_seeded_job_cards_match_planning_flags(seeded_client: TestClient) -> None:
    factory = seeded_client.app.state.session_factory  # type: ignore[attr-defined]
    with factory() as session:
        derived = maintenance_service.derive_jobs(load_snapshot(session, 10))
        seeded = maintenance_service.seeded_jobs(session)
    assert sorted(j.id for j in seeded) == sorted(j.id for j in derived)
    engines = _get(seeded_client, "/api/v1/engines", page_size=100)["items"]
    flagged = {e["id"] for e in engines if e["planning"]["status"] != "ok"}
    assert {j.engine_id for j in seeded} == flagged


def test_baseline_plan(seeded_client: TestClient) -> None:
    plan = _get(seeded_client, "/api/v1/maintenance/plan", buffer=WIDE)
    assert plan["method"] == "baseline"
    assert plan["status"] == "FEASIBLE" and plan["verified"] is True
    placed = {p["job_id"] for p in plan["placements"]} | {u["job_id"] for u in plan["unscheduled"]}
    assert placed == {j["id"] for j in plan["jobs"]}
    _check_plan_against_schedule(seeded_client, plan)
    c = plan["costs"]
    assert (
        c["total"]
        == c["cancellations"] + c["threshold"] + c["unscheduled"] + c["labor"] + c["transfers"]
    )


def test_scenario_lifecycle_and_comparison(seeded_client: TestClient) -> None:
    s = _run(seeded_client, {"buffer": WIDE})
    assert s["status"] == "solved" and s["error"] is None
    assert s["name"] == f"Buffer {WIDE}"
    base, opt = s["baseline"], s["optimized"]
    assert base["status"] == "FEASIBLE" and opt["status"] in ("OPTIMAL", "FEASIBLE")
    assert base["verified"] and opt["verified"]
    assert len(opt["jobs"]) > 0
    if opt["status"] == "OPTIMAL":
        assert opt["objective"] <= base["objective"]
    assert opt["costs"]["total"] == opt["objective"]
    _check_plan_against_schedule(seeded_client, opt)
    rows = {r["key"]: r for r in s["comparison"]}
    total = rows["total"]
    assert total["baseline"] == base["costs"]["total"]
    assert total["optimized"] == opt["costs"]["total"]
    assert total["delta"] == total["optimized"] - total["baseline"]
    if total["baseline"]:
        assert total["pct_change"] == pytest.approx(
            (total["optimized"] - total["baseline"]) / total["baseline"]
        )
    for p in opt["placements"]:
        assert p["why"], p
    listed = _get(seeded_client, "/api/v1/scenarios")
    assert listed[0]["id"] == s["id"] and listed[0]["optimized_status"] == opt["status"]


def test_scenario_changes_reach_constraints(seeded_client: TestClient) -> None:
    no_ord = _run(seeded_client, {"buffer": WIDE, "bay_changes": {"ORD": -2}})
    for method in ("baseline", "optimized"):
        assert all(p["facility"] != "ORD" for p in no_ord[method]["placements"])

    delayed = _run(seeded_client, {"buffer": WIDE, "part_delay_hours": 48})
    start = _ts(_get(seeded_client, "/api/v1/maintenance/resources")["horizon_start"])
    for p in delayed["optimized"]["placements"]:
        if p["part_lot"] == "SE-DEN-INBOUND":
            assert _ts(p["start"]) >= start + timedelta(hours=60 + 48)

    ships = sorted({j["aircraft_id"] for j in no_ord["optimized"]["jobs"]})
    grounded = _run(seeded_client, {"buffer": WIDE, "grounded_aircraft": [ships[0]]})
    metrics = grounded["optimized"]["metrics"]
    legs = _get(seeded_client, "/api/v1/flights", aircraft_id=ships[0], page_size=1000)["total"]
    assert metrics["grounded_legs"] == legs
    for p in grounded["optimized"]["placements"]:
        if p["aircraft_id"] == ships[0]:
            assert p["cancelled_flights"] == []
    _check_plan_against_schedule(seeded_client, grounded["optimized"], grounded=(ships[0],))

    engines = _get(seeded_client, "/api/v1/engines", page_size=100)["items"]
    free = next(e["aircraft_id"] for e in engines if e["aircraft_id"] not in ships)
    added = _run(
        seeded_client,
        {"buffer": WIDE, "added_jobs": [{"aircraft_id": free, "job_type": "borescope"}]},
    )
    assert f"MX-ADD-{free}" in {j["id"] for j in added["optimized"]["jobs"]}


def test_hard_policy_infeasible_is_explained(seeded_client: TestClient) -> None:
    s = _run(
        seeded_client,
        {"buffer": WIDE, "threshold_policy": "hard", "bay_changes": {"ORD": -2, "DEN": -2}},
    )
    assert s["status"] == "solved"
    opt, base = s["optimized"], s["baseline"]
    assert opt["status"] == "INFEASIBLE" and opt["placements"] == [] and not opt["verified"]
    assert opt["explanations"] and all(e["message"] for e in opt["explanations"])
    assert base["status"] == "NO_SOLUTION" and base["explanations"]
    assert all(r["delta"] is None and r["pct_change"] is None for r in s["comparison"])


@pytest.mark.parametrize(
    ("assumptions", "code"),
    [
        ({"bay_changes": {"XXX": 1}}, "unknown_facility"),
        ({"bay_changes": {"ORD": -3}}, "invalid_bay_change"),
        ({"grounded_aircraft": ["999"]}, "unknown_aircraft"),
        ({"part_delay_hours": 500}, "validation_error"),
        ({"time_limit_s": 0}, "validation_error"),
        ({"threshold_policy": "strict"}, "validation_error"),
    ],
)
def test_invalid_assumptions(
    seeded_client: TestClient, assumptions: dict[str, Any], code: str
) -> None:
    r = seeded_client.post("/api/v1/scenarios", json={"assumptions": assumptions})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == code


def test_added_job_on_ship_with_job_is_rejected(seeded_client: TestClient) -> None:
    jobs = _get(seeded_client, "/api/v1/maintenance/plan", buffer=WIDE)["jobs"]
    scenario = _run(seeded_client, {"buffer": WIDE})
    ship = scenario["optimized"]["jobs"][0]["aircraft_id"]
    assert jobs is not None
    r = seeded_client.post(
        "/api/v1/scenarios",
        json={
            "assumptions": {
                "buffer": WIDE,
                "added_jobs": [{"aircraft_id": ship, "job_type": "borescope"}],
            }
        },
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "duplicate_job"


def test_scenario_not_found_and_conflict(seeded_client: TestClient) -> None:
    assert seeded_client.get("/api/v1/scenarios/999999").json()["error"]["code"] == (
        "scenario_not_found"
    )
    assert seeded_client.post("/api/v1/scenarios/999999/solve").status_code == 404
    sid = seeded_client.post("/api/v1/scenarios", json={}).json()["id"]
    factory = seeded_client.app.state.session_factory  # type: ignore[attr-defined]
    from app import models

    with factory() as session:
        row = session.get(models.Scenario, sid)
        assert row is not None
        row.status = "running"
        session.commit()
    r = seeded_client.post(f"/api/v1/scenarios/{sid}/solve")
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_running"


def test_solver_failure_is_recorded(
    seeded_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_: Any, **__: Any) -> Any:
        raise RuntimeError("solver crashed")

    monkeypatch.setattr(maintenance_service, "solve", boom)
    sid = seeded_client.post("/api/v1/scenarios", json={}).json()["id"]
    seeded_client.post(f"/api/v1/scenarios/{sid}/solve")
    s = _get(seeded_client, f"/api/v1/scenarios/{sid}")
    assert s["status"] == "failed" and "solver crashed" in s["error"]
    assert s["optimized"] is None and s["comparison"] == []


def test_openapi_lists_maintenance_routes(seeded_client: TestClient) -> None:
    paths = _get(seeded_client, "/openapi.json")["paths"]
    for route in (
        "/api/v1/maintenance/resources",
        "/api/v1/maintenance/plan",
        "/api/v1/scenarios",
        "/api/v1/scenarios/{scenario_id}",
        "/api/v1/scenarios/{scenario_id}/solve",
    ):
        assert route in paths
