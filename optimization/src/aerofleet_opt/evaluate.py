"""Shared scoring and an independent constraint checker for any plan (heuristic or CP-SAT)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from aerofleet_opt.options import Option, lot_ready_slot, unscheduled_cycles_over
from aerofleet_opt.problem import Problem


@dataclass(frozen=True)
class Placement:
    job_id: str
    option: Option
    lot_id: str | None


@dataclass(frozen=True)
class Plan:
    placements: tuple[Placement, ...]
    unscheduled: tuple[str, ...]


@dataclass(frozen=True)
class Costs:
    cancellations: int
    threshold: int
    unscheduled: int
    labor: int
    transfers: int

    @property
    def total(self) -> int:
        return self.cancellations + self.threshold + self.unscheduled + self.labor + self.transfers


@dataclass(frozen=True)
class Metrics:
    jobs_total: int
    jobs_scheduled: int
    jobs_unscheduled: int
    thresholds_missed: int  # jobs whose aircraft flies past its planning threshold first
    cycles_over_threshold: int
    cancelled_legs: int  # cancelled to make room for maintenance
    grounded_legs: int  # cancelled because the scenario grounds an aircraft (same for any plan)
    labor_hours: int
    part_transfers: int
    bay_utilization: float  # occupied bay-hours / available bay-hours


def _lots(problem: Problem) -> dict[str, tuple[str, str]]:
    return {lot.id: (lot.part_type, lot.location) for lot in problem.lots}


def costs(problem: Problem, plan: Plan) -> Costs:
    w = problem.weights
    jobs = {j.id: j for j in problem.jobs}
    lots = _lots(problem)
    cancelled = sum(len(p.option.cancelled) for p in plan.placements)
    over = sum(p.option.cycles_over for p in plan.placements) + sum(
        unscheduled_cycles_over(problem, jobs[j]) for j in plan.unscheduled
    )
    transfers = sum(
        1
        for p in plan.placements
        if p.lot_id is not None and lots[p.lot_id][1] != p.option.facility
    )
    return Costs(
        cancellations=cancelled * w.cancelled_leg,
        threshold=over * w.cycle_over_threshold,
        unscheduled=len(plan.unscheduled) * w.unscheduled_job,
        labor=sum(p.option.labor_cost for p in plan.placements),
        transfers=transfers * w.part_transfer,
    )


def metrics(problem: Problem, plan: Plan) -> Metrics:
    jobs = {j.id: j for j in problem.jobs}
    lots = _lots(problem)
    over_sched = [p.option.cycles_over for p in plan.placements]
    over_unsched = [unscheduled_cycles_over(problem, jobs[j]) for j in plan.unscheduled]
    bay_hours = sum(p.option.end - p.option.start for p in plan.placements)
    capacity = sum(f.bays for f in problem.facilities) * problem.horizon_slots
    return Metrics(
        jobs_total=len(problem.jobs),
        jobs_scheduled=len(plan.placements),
        jobs_unscheduled=len(plan.unscheduled),
        thresholds_missed=sum(1 for c in [*over_sched, *over_unsched] if c > 0),
        cycles_over_threshold=sum(over_sched) + sum(over_unsched),
        cancelled_legs=sum(len(p.option.cancelled) for p in plan.placements),
        grounded_legs=sum(len(a.legs) for a in problem.aircraft if a.grounded),
        labor_hours=sum(p.option.labor_hours for p in plan.placements),
        part_transfers=sum(
            1
            for p in plan.placements
            if p.lot_id is not None and lots[p.lot_id][1] != p.option.facility
        ),
        bay_utilization=bay_hours / capacity if capacity else 0.0,
    )


def verify(problem: Problem, plan: Plan) -> list[str]:
    """Return every hard-constraint violation. An empty list means the plan is feasible."""
    errors: list[str] = []
    jobs = {j.id: j for j in problem.jobs}
    aircraft = problem.aircraft_by_id()
    facilities = problem.facility_by_code()
    lots = {lot.id: lot for lot in problem.lots}

    seen = [p.job_id for p in plan.placements] + list(plan.unscheduled)
    if sorted(seen) != sorted(jobs):
        errors.append("every job must be placed or unscheduled exactly once")
    if problem.threshold_policy == "hard":
        errors += [f"{j}: unscheduled under hard threshold policy" for j in plan.unscheduled]

    bays: dict[tuple[str, int], int] = defaultdict(int)
    techs: dict[tuple[str, int], int] = defaultdict(int)
    lot_use: dict[str, int] = defaultdict(int)
    for p in plan.placements:
        job, opt = jobs[p.job_id], p.option
        fac = facilities.get(opt.facility)
        if fac is None or job.job_type not in fac.supports:
            errors.append(f"{job.id}: {opt.facility} cannot do {job.job_type}")
            continue
        if opt.start < 0 or opt.end > problem.horizon_slots:
            errors.append(f"{job.id}: outside the horizon")
        if opt.end - opt.start != job.duration_slots:
            errors.append(f"{job.id}: duration mismatch")
        if problem.threshold_policy == "hard" and opt.cycles_over > 0:
            errors.append(f"{job.id}: {opt.cycles_over} cycles over threshold under hard policy")
        for s in range(opt.start, opt.end):
            bays[(opt.facility, s)] += 1
            techs[(opt.facility, s)] += job.technicians
        if job.part_type is None:
            if p.lot_id is not None:
                errors.append(f"{job.id}: consumes a part it does not need")
        else:
            lot = lots.get(p.lot_id or "")
            if lot is None or lot.part_type != job.part_type:
                errors.append(f"{job.id}: needs {job.part_type}")
            else:
                lot_use[lot.id] += 1
                if lot_ready_slot(lot, opt.facility) > opt.start:
                    errors.append(f"{job.id}: part {lot.id} not at {opt.facility} by start")
        errors += _check_aircraft(problem, aircraft[job.aircraft_id].id, p, plan)

    for (code, s), used in bays.items():
        if used > facilities[code].bays:
            errors.append(f"{code} slot {s}: {used} jobs > {facilities[code].bays} bays")
    for (code, s), used in techs.items():
        if used > facilities[code].technicians[s]:
            errors.append(
                f"{code} slot {s}: {used} technicians > {facilities[code].technicians[s]}"
            )
    for lot_id, used in lot_use.items():
        if used > lots[lot_id].quantity:
            errors.append(f"lot {lot_id}: {used} used > {lots[lot_id].quantity}")
    return errors


def _check_aircraft(problem: Problem, aircraft_id: str, p: Placement, plan: Plan) -> list[str]:
    """Aircraft at the facility at job start, no kept leg overlaps the job, continuity holds."""
    ac = problem.aircraft_by_id()[aircraft_id]
    cancelled = set(p.option.cancelled)
    kept = [leg for leg in problem.flown_legs(ac) if leg.id not in cancelled]
    errors: list[str] = []
    station = ac.initial_station
    for leg in kept:
        if leg.origin != station:
            errors.append(f"{p.job_id}: {leg.id} departs {leg.origin} but aircraft is at {station}")
        station = leg.destination
    start, end = problem.time_of(p.option.start), problem.time_of(p.option.end)
    location = ac.initial_station
    for leg in kept:
        if leg.departure < end and leg.arrival > start:
            errors.append(f"{p.job_id}: {leg.id} flies during maintenance")
        if leg.arrival <= start:
            location = leg.destination
    if location != p.option.facility:
        errors.append(f"{p.job_id}: aircraft at {location}, not {p.option.facility}, at start")
    return errors
