"""Hard constraints, statuses, objective accounting and explanations for both planners."""

from __future__ import annotations

from dataclasses import replace

import pytest

from aerofleet_opt import fixtures as fx
from aerofleet_opt.compare import percent_change, run_baseline, run_optimizer
from aerofleet_opt.cpsat import SolveResult, solve_cpsat
from aerofleet_opt.evaluate import Placement, Plan, costs, verify
from aerofleet_opt.heuristic import solve_heuristic
from aerofleet_opt.options import enumerate_options
from aerofleet_opt.problem import PartLot


def test_feasible_fixture_both_methods_verified() -> None:
    p = fx.feasible()
    base, opt = run_baseline(p), run_optimizer(p, 5)
    assert base.status == "FEASIBLE"
    assert opt.status == "OPTIMAL"
    assert base.violations == () and opt.violations == ()
    assert base.plan is not None and opt.plan is not None
    assert base.plan.unscheduled == () and opt.plan.unscheduled == ()
    assert opt.objective is not None and base.objective is not None
    assert opt.objective <= base.objective


def test_objective_components_sum_to_solver_objective() -> None:
    p = fx.feasible()
    result = solve_cpsat(p)
    assert result.plan is not None and result.objective is not None
    c = costs(p, result.plan)
    assert c.total == result.objective
    assert c.total == c.cancellations + c.threshold + c.unscheduled + c.labor + c.transfers


def test_heuristic_is_deterministic() -> None:
    p = fx.random_problem(7)
    assert solve_heuristic(p) == solve_heuristic(p)


def test_cpsat_is_reproducible() -> None:
    p = fx.random_problem(11)
    assert solve_cpsat(p).plan == solve_cpsat(p).plan


def test_single_bay_never_double_booked() -> None:
    p = fx.feasible()
    for plan in (solve_heuristic(p), solve_cpsat(p).plan):
        assert plan is not None
        a, b = plan.placements
        assert a.option.end <= b.option.start or b.option.end <= a.option.start


def test_technician_roster_respected() -> None:
    # Night shift has 2 technicians; an engine change needs 4, so it must sit entirely in day slots.
    p = fx.feasible()
    p = replace(p, facilities=(fx.facility(bays=2, day=8, night=2),))
    for plan in (solve_heuristic(p), solve_cpsat(p).plan):
        assert plan is not None
        change = next(x for x in plan.placements if x.job_id == "J-A1")
        assert not any(
            p.facilities[0].night[s] for s in range(change.option.start, change.option.end)
        )
        assert verify(p, plan) == []


def test_part_lead_time_and_quantity() -> None:
    p = fx.feasible()
    # One spare, only usable from slot 20: the engine change cannot start earlier.
    p = replace(p, lots=(PartLot("L1", fx.SPARE, "HUB", 1, 20, 12),))
    for plan in (solve_heuristic(p), solve_cpsat(p).plan):
        assert plan is not None
        change = next(x for x in plan.placements if x.job_id == "J-A1")
        assert change.option.start >= 20 and change.lot_id == "L1"
    # No spares at all: the job is unscheduled (penalty policy) and explained.
    empty = replace(p, lots=())
    opt = run_optimizer(empty, 5)
    assert opt.plan is not None and opt.plan.unscheduled == ("J-A1",)
    assert "spare_engine" in opt.reasons["J-A1"][0]


def test_part_transfer_counts_lead_time() -> None:
    p = fx.feasible()
    p = replace(p, lots=(PartLot("FAR", fx.SPARE, "OUT", 1, 0, 30),))
    plan = solve_cpsat(p).plan
    assert plan is not None
    change = next(x for x in plan.placements if x.job_id == "J-A1")
    assert change.option.start >= 30
    assert costs(p, plan).transfers == p.weights.part_transfer


def test_incompatible_facility_is_diagnosed() -> None:
    p = fx.no_facility()
    opt = run_optimizer(p, 5)
    assert opt.plan is not None and opt.plan.unscheduled == ("J-A1",)
    assert "engine_change" in opt.reasons["J-A1"][0]
    hard = replace(p, threshold_policy="hard")
    result = run_optimizer(hard, 5)
    assert result.status == "INFEASIBLE"
    assert [e.code for e in result.explanations] == ["no_compatible_facility"]


def test_deliberately_infeasible_fixture_is_explained() -> None:
    p = fx.infeasible_hard()
    # Each job alone is feasible...
    for job in p.jobs:
        assert solve_cpsat(replace(p, jobs=(job,))).status == "OPTIMAL"
    # ...together they are not, and the core names both.
    result = solve_cpsat(p)
    assert result.status == "INFEASIBLE" and result.plan is None
    assert set(result.conflicting_jobs) == {"J-A1", "J-B1"}
    opt = run_optimizer(p, 5)
    assert opt.status == "INFEASIBLE"
    (explanation,) = opt.explanations
    assert explanation.code == "resource_conflict"
    assert "ENG-A1" in explanation.message and "1 bay" in explanation.message
    base = run_baseline(p)
    assert base.status == "NO_SOLUTION" and base.plan is None and base.explanations


def test_penalty_policy_turns_conflict_into_cost() -> None:
    p = replace(fx.infeasible_hard(), threshold_policy="penalty")
    opt = run_optimizer(p, 5)
    assert opt.status == "OPTIMAL" and opt.violations == ()
    assert opt.metrics is not None
    assert opt.metrics.thresholds_missed + opt.metrics.cancelled_legs > 0


def test_cancellation_block_preserves_location_continuity() -> None:
    p = fx.feasible()
    job = p.jobs[0]
    cancelling = [o for o in enumerate_options(p, job) if o.cancelled]
    assert cancelling
    for opt in cancelling:
        plan = Plan((Placement(job.id, opt, "L1"),), tuple(j.id for j in p.jobs[1:]))
        assert verify(p, plan) == []


def test_verify_catches_violations() -> None:
    p = fx.feasible()
    plan = solve_heuristic(p)
    a = plan.placements[0]
    clash = Placement(
        plan.placements[1].job_id,
        replace(plan.placements[1].option, start=a.option.start, end=a.option.start + 4),
        None,
    )
    bad = Plan((a, clash), ())
    assert any("bays" in e for e in verify(p, bad))
    no_part = Plan((replace(a, lot_id=None), plan.placements[1]), ())
    assert any("needs spare_engine" in e for e in verify(p, no_part))


def test_time_limit_unknown_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    import aerofleet_opt.compare as compare

    monkeypatch.setattr(
        compare,
        "solve_cpsat",
        lambda problem, time_limit_s: SolveResult("UNKNOWN", None, None, None, 1, ()),
    )
    result = compare.run_optimizer(fx.feasible(), 0.5)
    assert result.status == "UNKNOWN" and result.plan is None
    assert result.explanations[0].code == "time_limit"


@pytest.mark.parametrize("seed", range(25))
@pytest.mark.parametrize("policy", ["penalty", "hard"])
def test_random_instances_respect_all_constraints(seed: int, policy: str) -> None:
    p = fx.random_problem(seed, "hard" if policy == "hard" else "penalty")
    base, opt = run_baseline(p), run_optimizer(p, 10)
    assert base.violations == () and opt.violations == ()
    if opt.plan is not None:
        assert opt.costs is not None and opt.costs.total == opt.objective
    else:
        assert opt.status == "INFEASIBLE" and opt.explanations
    if base.objective is not None and opt.status == "OPTIMAL":
        assert opt.objective is not None and opt.objective <= base.objective
    if policy == "hard" and base.status == "FEASIBLE":
        assert opt.status in ("OPTIMAL", "FEASIBLE")
    if policy == "penalty":
        assert base.status == "FEASIBLE" and opt.plan is not None


def test_percent_change_guards_zero() -> None:
    assert percent_change(0, 5) is None
    assert percent_change(200, 150) == pytest.approx(-0.25)
    assert percent_change(-100, -50) == pytest.approx(0.5)


def test_problem_validation() -> None:
    p = fx.feasible()
    with pytest.raises(ValueError, match="one maintenance job per aircraft"):
        replace(p, jobs=(p.jobs[0], replace(p.jobs[1], aircraft_id="A1")))
    with pytest.raises(ValueError, match="roster length"):
        replace(p, horizon_slots=24)
