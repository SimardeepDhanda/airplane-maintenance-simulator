"""Run the baseline and CP-SAT on one problem and package comparable, verified results."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

from aerofleet_opt.cpsat import solve_cpsat
from aerofleet_opt.evaluate import Costs, Metrics, Plan, costs, metrics, verify
from aerofleet_opt.explain import (
    Explanation,
    diagnose,
    explain_conflict,
    explain_placement,
    explain_unscheduled,
)
from aerofleet_opt.heuristic import solve_heuristic
from aerofleet_opt.problem import Problem

MethodStatus = Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "NO_SOLUTION"]


@dataclass(frozen=True)
class MethodResult:
    method: Literal["baseline", "optimized"]
    status: MethodStatus
    plan: Plan | None
    costs: Costs | None
    metrics: Metrics | None
    objective: int | None
    best_bound: float | None
    wall_ms: int
    violations: tuple[str, ...]  # independent check; must be empty for a returned plan
    reasons: dict[str, list[str]]  # job id -> why it sits where it does / why unscheduled
    explanations: tuple[Explanation, ...]  # infeasibility or no-solution explanations


def _name(problem: Problem, job_id: str) -> str:
    job = next(j for j in problem.jobs if j.id == job_id)
    return job.engine_id or job.aircraft_id


def _reasons(problem: Problem, plan: Plan) -> dict[str, list[str]]:
    out = {p.job_id: explain_placement(problem, plan, p) for p in plan.placements}
    for job_id in plan.unscheduled:
        out[job_id] = [explain_unscheduled(problem, plan, job_id)]
    return out


def run_baseline(problem: Problem) -> MethodResult:
    started = time.perf_counter()
    plan = solve_heuristic(problem)
    wall_ms = round((time.perf_counter() - started) * 1000)
    if problem.threshold_policy == "hard" and plan.unscheduled:
        diag = [d for d in diagnose(problem) if d.job_id in plan.unscheduled]
        missing = [
            Explanation(
                j,
                "heuristic_no_slot",
                f"{_name(problem, j)}: {explain_unscheduled(problem, plan, j)}",
            )
            for j in plan.unscheduled
            if j not in {d.job_id for d in diag}
        ]
        return MethodResult(
            "baseline",
            "NO_SOLUTION",
            None,
            None,
            None,
            None,
            None,
            wall_ms,
            (),
            {},
            tuple(diag + missing),
        )
    c = costs(problem, plan)
    return MethodResult(
        method="baseline",
        status="FEASIBLE",
        plan=plan,
        costs=c,
        metrics=metrics(problem, plan),
        objective=c.total,
        best_bound=None,
        wall_ms=wall_ms,
        violations=tuple(verify(problem, plan)),
        reasons=_reasons(problem, plan),
        explanations=(),
    )


def run_optimizer(problem: Problem, time_limit_s: float) -> MethodResult:
    result = solve_cpsat(problem, time_limit_s=time_limit_s)
    if result.plan is None:
        explanations = diagnose(problem)
        if result.status == "INFEASIBLE" and not explanations and result.conflicting_jobs:
            explanations = [explain_conflict(problem, result.conflicting_jobs)]
        if result.status == "UNKNOWN":
            explanations = [
                Explanation(None, "time_limit", f"No solution within {time_limit_s:g} s")
            ]
        return MethodResult(
            "optimized",
            result.status,
            None,
            None,
            None,
            None,
            None,
            result.wall_ms,
            (),
            {},
            tuple(explanations),
        )
    c = costs(problem, result.plan)
    return MethodResult(
        method="optimized",
        status=result.status,
        plan=result.plan,
        costs=c,
        metrics=metrics(problem, result.plan),
        objective=result.objective,
        best_bound=result.best_bound,
        wall_ms=result.wall_ms,
        violations=tuple(verify(problem, result.plan)),
        reasons=_reasons(problem, result.plan),
        explanations=(),
    )


def percent_change(baseline: float, optimized: float) -> float | None:
    """Relative change; None when the baseline is zero (undefined, not 0% or infinity)."""
    if baseline == 0:
        return None
    return (optimized - baseline) / abs(baseline)
