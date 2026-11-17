"""OR-Tools CP-SAT model over the same placement options as the baseline.

Decision variables: one optional fixed-size interval per (job, facility, start) and, for jobs that
need a part, one boolean per compatible part lot. Bays and technicians are cumulative resources per
facility; technician shifts with fewer people than the facility's peak are modelled as fixed
"blocking" intervals. Under the hard threshold policy each job gets an assumption literal so an
infeasible model returns the subset of jobs that cannot all be met (an infeasibility core).

Runs single-threaded with a fixed seed by default so results are reproducible. FEASIBLE means an
incumbent found within the time limit, not a proven optimum.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

from ortools.sat.python import cp_model

from aerofleet_opt.evaluate import Placement, Plan
from aerofleet_opt.options import Option, enumerate_options, lot_ready_slot, unscheduled_cycles_over
from aerofleet_opt.problem import Problem

SolverStatus = Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN"]

_STATUS: dict[cp_model.CpSolverStatus, SolverStatus] = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.UNKNOWN: "UNKNOWN",
}


@dataclass(frozen=True)
class SolveResult:
    status: SolverStatus
    plan: Plan | None
    objective: int | None
    best_bound: float | None
    wall_ms: int
    conflicting_jobs: tuple[str, ...]  # infeasibility core (hard policy), else empty


@dataclass
class _Choice:
    option: Option
    present: cp_model.IntVar
    lots: list[tuple[str, cp_model.IntVar]]


def solve_cpsat(
    problem: Problem,
    time_limit_s: float = 10.0,
    workers: int = 1,
    seed: int = 0,
    *,
    minimize_core: bool = True,
) -> SolveResult:
    started = time.perf_counter()
    result = _solve(problem, time_limit_s, workers, seed, None)
    if not (minimize_core and result.status == "INFEASIBLE" and len(result.conflicting_jobs) > 1):
        return result
    # Deletion filter: drop each job from the core if the rest is still infeasible. Leaves an
    # irreducible set (every remaining job is needed for the conflict).
    core = list(result.conflicting_jobs)
    per_check = max(0.5, time_limit_s / (2 * len(core)))
    for job_id in list(core):
        trial = [j for j in core if j != job_id]
        if _solve(problem, per_check, workers, seed, frozenset(trial)).status == "INFEASIBLE":
            core = trial
    wall_ms = round((time.perf_counter() - started) * 1000)
    return SolveResult(result.status, None, None, None, wall_ms, tuple(sorted(core)))


def _solve(
    problem: Problem,
    time_limit_s: float,
    workers: int,
    seed: int,
    hard_jobs: frozenset[str] | None,
) -> SolveResult:
    """hard_jobs: jobs that must be on time (None: all jobs under the hard policy, else none)."""
    started = time.perf_counter()
    m = cp_model.CpModel()
    w = problem.weights
    if hard_jobs is None:
        hard_jobs = (
            frozenset(j.id for j in problem.jobs)
            if problem.threshold_policy == "hard"
            else frozenset()
        )
    facilities = problem.facility_by_code()

    choices: dict[str, list[_Choice]] = {}
    unscheduled: dict[str, cp_model.IntVar] = {}
    assumptions: dict[str, cp_model.IntVar] = {}
    objective: list[cp_model.LinearExprT] = []
    lot_users: dict[str, list[cp_model.IntVar]] = {lot.id: [] for lot in problem.lots}
    by_facility: dict[str, list[tuple[cp_model.IntervalVar, int]]] = {
        f.code: [] for f in problem.facilities
    }

    for job in problem.jobs:
        u = m.new_bool_var(f"u[{job.id}]")
        unscheduled[job.id] = u
        objective.append(
            u * (w.unscheduled_job + unscheduled_cycles_over(problem, job) * w.cycle_over_threshold)
        )
        on_time: cp_model.IntVar | None = None
        if job.id in hard_jobs:
            on_time = m.new_bool_var(f"on_time[{job.id}]")
            assumptions[job.id] = on_time
            m.add(u == 0).only_enforce_if(on_time)
        job_choices: list[_Choice] = []
        for opt in enumerate_options(problem, job):
            lots: list[tuple[str, cp_model.IntVar]] = []
            if job.part_type is not None:
                usable = [
                    lot
                    for lot in problem.lots
                    if lot.part_type == job.part_type
                    and lot.quantity > 0
                    and lot_ready_slot(lot, opt.facility) <= opt.start
                ]
                if not usable:
                    continue
                for lot in usable:
                    x = m.new_bool_var(f"x[{job.id},{opt.facility},{opt.start},{lot.id}]")
                    lots.append((lot.id, x))
                    lot_users[lot.id].append(x)
                    if lot.location != opt.facility:
                        objective.append(x * w.part_transfer)
            present = m.new_bool_var(f"y[{job.id},{opt.facility},{opt.start}]")
            if lots:
                m.add(present == sum(x for _, x in lots))
            if on_time is not None and opt.cycles_over > 0:
                m.add(present == 0).only_enforce_if(on_time)
            interval = m.new_optional_fixed_size_interval_var(
                opt.start, job.duration_slots, present, f"i[{job.id},{opt.facility},{opt.start}]"
            )
            by_facility[opt.facility].append((interval, job.technicians))
            cost = (
                len(opt.cancelled) * w.cancelled_leg
                + opt.cycles_over * w.cycle_over_threshold
                + opt.labor_cost
            )
            objective.append(present * cost)
            job_choices.append(_Choice(opt, present, lots))
        m.add_exactly_one([c.present for c in job_choices] + [u])
        choices[job.id] = job_choices

    for code, items in by_facility.items():
        fac = facilities[code]
        if not items:
            continue
        intervals = [i for i, _ in items]
        m.add_cumulative(intervals, [1] * len(items), fac.bays)
        peak = max(fac.technicians)
        blockers = _shift_blockers(m, code, fac.technicians, peak)
        m.add_cumulative(
            intervals + [b for b, _ in blockers],
            [d for _, d in items] + [d for _, d in blockers],
            peak,
        )
    for lot in problem.lots:
        if lot_users[lot.id]:
            m.add(sum(lot_users[lot.id]) <= lot.quantity)

    m.minimize(sum(objective))
    if assumptions:
        m.add_assumptions(list(assumptions.values()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = seed
    status = _STATUS.get(solver.solve(m), "UNKNOWN")
    wall_ms = round((time.perf_counter() - started) * 1000)

    if status in ("OPTIMAL", "FEASIBLE"):
        placements: list[Placement] = []
        missing: list[str] = []
        for job in problem.jobs:
            chosen = next((c for c in choices[job.id] if solver.boolean_value(c.present)), None)
            if chosen is None:
                missing.append(job.id)
                continue
            lot_id = next((lid for lid, x in chosen.lots if solver.boolean_value(x)), None)
            placements.append(Placement(job.id, chosen.option, lot_id))
        return SolveResult(
            status=status,
            plan=Plan(tuple(placements), tuple(sorted(missing))),
            objective=round(solver.objective_value),
            best_bound=solver.best_objective_bound,
            wall_ms=wall_ms,
            conflicting_jobs=(),
        )

    core: tuple[str, ...] = ()
    if status == "INFEASIBLE" and assumptions:
        index_to_job = {v.index: j for j, v in assumptions.items()}
        core = tuple(
            sorted(
                index_to_job[i]
                for i in solver.sufficient_assumptions_for_infeasibility()
                if i in index_to_job
            )
        )
    return SolveResult(status, None, None, None, wall_ms, core)


def _shift_blockers(
    m: cp_model.CpModel, code: str, roster: tuple[int, ...], peak: int
) -> list[tuple[cp_model.IntervalVar, int]]:
    """Fixed intervals that occupy the technicians missing from each slot vs the peak roster."""
    out: list[tuple[cp_model.IntervalVar, int]] = []
    s = 0
    while s < len(roster):
        deficit = peak - roster[s]
        e = s
        while e < len(roster) and peak - roster[e] == deficit:
            e += 1
        if deficit > 0:
            out.append((m.new_fixed_size_interval_var(s, e - s, f"shift[{code},{s}]"), deficit))
        s = e
    return out
