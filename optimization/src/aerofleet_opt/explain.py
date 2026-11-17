"""Explanations computed from the actual constraints, never canned text.

- `diagnose`: per-job structural problems found before solving (no compatible facility on the
  aircraft's route, no part can arrive in time, threshold unreachable under the hard policy).
- `explain_conflict`: turns a CP-SAT infeasibility core into the shared resources involved.
- `explain_placement`: why a job sits where it does, including what blocks the earliest
  alternative given the rest of the plan.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from aerofleet_opt.evaluate import Placement, Plan
from aerofleet_opt.heuristic import due_hours
from aerofleet_opt.options import Option, enumerate_options, lot_ready_slot
from aerofleet_opt.problem import Job, Problem


@dataclass(frozen=True)
class Explanation:
    job_id: str | None
    code: str
    message: str


def utc(when: datetime) -> str:
    return f"{when.day} {when:%b %H:%MZ}"


def _label(job: Job) -> str:
    return job.engine_id or job.aircraft_id


def _part_ready(problem: Problem, job: Job, opt: Option) -> bool:
    return job.part_type is None or any(
        lot.part_type == job.part_type
        and lot.quantity > 0
        and lot_ready_slot(lot, opt.facility) <= opt.start
        for lot in problem.lots
    )


def _static_fit(problem: Problem, job: Job, opt: Option) -> bool:
    fac = problem.facility_by_code()[opt.facility]
    return fac.bays > 0 and all(
        fac.technicians[s] >= job.technicians for s in range(opt.start, opt.end)
    )


def _due_text(problem: Problem, job: Job) -> str:
    ac = problem.aircraft_by_id()[job.aircraft_id]
    legs = problem.flown_legs(ac)
    if job.threshold_leg is None or job.threshold_leg >= len(legs):
        return "end of horizon"
    leg = legs[job.threshold_leg]
    return f"{leg.flight_number} departs {leg.origin} {utc(leg.departure)}"


def diagnose(problem: Problem) -> list[Explanation]:
    out: list[Explanation] = []
    aircraft = problem.aircraft_by_id()
    for job in problem.jobs:
        ac = aircraft[job.aircraft_id]
        options = enumerate_options(problem, job)
        name = _label(job)
        if not options:
            stations = sorted(
                {ac.initial_station} | {leg.destination for leg in problem.flown_legs(ac)}
            )
            capable = sorted(f.code for f in problem.facilities if job.job_type in f.supports)
            out.append(
                Explanation(
                    job.id,
                    "no_compatible_facility",
                    f"{name}: {job.job_type} needs {'/'.join(capable) or 'a capable facility'}; "
                    f"ship {ac.id} is only on the ground at {', '.join(stations)} with "
                    f"{job.duration_slots} h free before the horizon ends",
                )
            )
            continue
        with_part = [o for o in options if _part_ready(problem, job, o)]
        if not with_part:
            lots = [lot for lot in problem.lots if lot.part_type == job.part_type]
            latest = max(options, key=lambda o: o.start)
            stock = (
                ", ".join(
                    f"{lot.quantity} at {lot.location} from {utc(problem.time_of(lot.ready_slot))}"
                    for lot in lots
                )
                or "none in stock"
            )
            out.append(
                Explanation(
                    job.id,
                    "part_unavailable",
                    f"{name}: no {job.part_type} reaches a usable slot "
                    f"(latest start {utc(problem.time_of(latest.start))} at {latest.facility}; "
                    f"stock: {stock})",
                )
            )
            continue
        fitting = [o for o in with_part if _static_fit(problem, job, o)]
        if not fitting:
            out.append(
                Explanation(
                    job.id,
                    "no_capacity",
                    f"{name}: every reachable slot lacks a bay or {job.technicians} technicians "
                    f"on shift",
                )
            )
            continue
        if problem.threshold_policy == "hard":
            on_time = [o for o in fitting if o.cycles_over == 0]
            if not on_time:
                first = min(fitting, key=lambda o: o.start)
                out.append(
                    Explanation(
                        job.id,
                        "threshold_unreachable",
                        f"{name}: must start before {_due_text(problem, job)}; earliest slot with "
                        f"a bay, crew and part is {utc(problem.time_of(first.start))} at "
                        f"{first.facility}",
                    )
                )
    return out


def explain_conflict(problem: Problem, core: tuple[str, ...]) -> Explanation:
    """Summarise why the jobs in an infeasibility core cannot all be met together."""
    jobs = {j.id: j for j in problem.jobs}
    facilities = problem.facility_by_code()
    stations: dict[str, list[str]] = defaultdict(list)
    for job_id in core:
        job = jobs[job_id]
        for code in sorted(
            {
                o.facility
                for o in enumerate_options(problem, job)
                if o.cycles_over == 0 and _part_ready(problem, job, o)
            }
        ):
            stations[code].append(_label(job))
    parts = []
    for code, names in sorted(stations.items()):
        fac = facilities[code]
        lo, hi = min(fac.technicians), max(fac.technicians)
        crew = f"{lo} technicians" if lo == hi else f"{lo} to {hi} technicians by shift"
        parts.append(
            f"{code} ({', '.join(names)}): {fac.bays} bay{'s' if fac.bays != 1 else ''}, {crew}"
        )
    needed = sorted({p for j in core if (p := jobs[j].part_type) is not None})
    for part in needed:
        lots = [lot for lot in problem.lots if lot.part_type == part and lot.quantity > 0]
        stock = ", ".join(
            f"{lot.quantity} at {lot.location} from {utc(problem.time_of(lot.ready_slot))}"
            for lot in lots
        )
        parts.append(f"{part}: {stock or 'none'}")
    due = "; ".join(f"{_label(jobs[j])} before {_due_text(problem, jobs[j])}" for j in core)
    return Explanation(
        None,
        "resource_conflict",
        f"Cannot all be on time: {due}. Shared: {' | '.join(parts) or 'nothing reachable'}",
    )


def explain_placement(problem: Problem, plan: Plan, placement: Placement) -> list[str]:
    jobs = {j.id: j for j in problem.jobs}
    job = jobs[placement.job_id]
    opt = placement.option
    ac = problem.aircraft_by_id()[job.aircraft_id]
    legs = {leg.id: leg for leg in ac.legs}
    reasons: list[str] = []
    if opt.cancelled:
        first, last = legs[opt.cancelled[0]], legs[opt.cancelled[-1]]
        reasons.append(
            f"Cancels {len(opt.cancelled)} leg{'s' if len(opt.cancelled) > 1 else ''} "
            f"({first.flight_number} {utc(first.departure)} to {last.flight_number}); "
            f"ship returns to {opt.facility} {utc(last.arrival)}"
        )
    else:
        until = (
            utc(problem.time_of(opt.on_ground_until))
            if opt.on_ground_until is not None
            else "end of horizon"
        )
        reasons.append(f"Fits ground time at {opt.facility} (next departure {until})")
    if opt.cycles_over:
        reasons.append(
            f"Flies {opt.cycles_over} cycle(s) past threshold ({_due_text(problem, job)})"
        )
    elif job.threshold_leg is not None:
        reasons.append(f"Before threshold ({_due_text(problem, job)})")
    if placement.lot_id is not None:
        lot = next(lot for lot in problem.lots if lot.id == placement.lot_id)
        if lot.location == opt.facility:
            reasons.append(f"{job.part_type} from {lot.location} stock")
        else:
            reasons.append(f"{job.part_type} moved from {lot.location} ({lot.transfer_slots} h)")
    blocker = _earliest_alternative(problem, plan, placement)
    if blocker:
        reasons.append(blocker)
    return reasons


def explain_unscheduled(problem: Problem, plan: Plan, job_id: str) -> str:
    job = next(j for j in problem.jobs if j.id == job_id)
    diag = next((d for d in diagnose(problem) if d.job_id == job_id), None)
    if diag is not None:
        return diag.message
    probe = Placement(job_id, _dummy(problem, job), None)
    return _earliest_alternative(problem, plan, probe, include_all=True) or "No feasible slot"


def _dummy(problem: Problem, job: Job) -> Option:
    return Option(job.id, "", problem.horizon_slots, problem.horizon_slots, 0, (), 0, 0, 0, None)


def _earliest_alternative(
    problem: Problem, plan: Plan, placement: Placement, include_all: bool = False
) -> str | None:
    """What stops this job starting earlier, given every other job's placement."""
    job = next(j for j in problem.jobs if j.id == placement.job_id)
    if problem.threshold_policy == "hard":
        candidates = [o for o in enumerate_options(problem, job) if o.cycles_over == 0]
    else:
        candidates = enumerate_options(problem, job)
    earlier = sorted(
        (o for o in candidates if o.start < placement.option.start), key=lambda o: o.start
    )
    if not earlier:
        return None
    alt = earlier[0]
    facilities = problem.facility_by_code()
    fac = facilities[alt.facility]
    others = [
        p for p in plan.placements if p.job_id != job.id and p.option.facility == alt.facility
    ]
    when = utc(problem.time_of(alt.start))
    for s in range(alt.start, alt.end):
        busy = [p for p in others if p.option.start <= s < p.option.end]
        if len(busy) + 1 > fac.bays:
            names = ", ".join(
                _label(next(j for j in problem.jobs if j.id == p.job_id)) for p in busy
            )
            return f"Earliest option ({alt.facility} {when}) blocked: bays in use by {names}"
        crew = sum(next(j for j in problem.jobs if j.id == p.job_id).technicians for p in busy)
        if crew + job.technicians > fac.technicians[s]:
            return (
                f"Earliest option ({alt.facility} {when}) blocked: "
                f"{fac.technicians[s]} technicians on shift at {utc(problem.time_of(s))}, "
                f"{crew} already assigned, job needs {job.technicians}"
            )
    if not _part_ready(problem, job, alt):
        return f"Earliest option ({alt.facility} {when}) blocked: no {job.part_type} there yet"
    used: dict[str, int] = defaultdict(int)
    for p in plan.placements:
        if p.lot_id is not None and p.job_id != job.id:
            used[p.lot_id] += 1
    if job.part_type is not None and not any(
        lot.part_type == job.part_type
        and lot_ready_slot(lot, alt.facility) <= alt.start
        and used[lot.id] < lot.quantity
        for lot in problem.lots
    ):
        return f"Earliest option ({alt.facility} {when}) blocked: {job.part_type} stock committed"
    if include_all:
        return f"Earliest option ({alt.facility} {when}) not chosen: lower total cost elsewhere"
    chosen = placement.option
    delta = _option_cost(problem, alt) - _option_cost(problem, chosen)
    if delta <= 0:
        return None
    terms = []
    if len(alt.cancelled) != len(chosen.cancelled):
        terms.append(f"{len(alt.cancelled) - len(chosen.cancelled):+d} cancelled legs")
    if alt.cycles_over != chosen.cycles_over:
        terms.append(f"{alt.cycles_over - chosen.cycles_over:+d} cycles over threshold")
    if alt.labor_cost != chosen.labor_cost:
        terms.append(f"labour {alt.labor_cost - chosen.labor_cost:+d}")
    return f"Earliest option ({alt.facility} {when}) costs {delta} more: {', '.join(terms)}"


def _option_cost(problem: Problem, opt: Option) -> int:
    w = problem.weights
    return (
        len(opt.cancelled) * w.cancelled_leg
        + opt.cycles_over * w.cycle_over_threshold
        + (opt.labor_cost)
    )


__all__ = [
    "Explanation",
    "diagnose",
    "due_hours",
    "explain_conflict",
    "explain_placement",
    "explain_unscheduled",
    "utc",
]
