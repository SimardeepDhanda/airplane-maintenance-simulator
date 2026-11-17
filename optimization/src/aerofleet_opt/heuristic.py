"""Transparent baseline: earliest planning due date first, each job in its first feasible slot.

Deterministic: jobs are ordered by (due time, job id); options by (start, facility code); parts
prefer a local lot, then the earliest-ready lot, then lot id. Cost is ignored except that, under
the hard threshold policy, options that fly past the threshold are skipped.
"""

from __future__ import annotations

from collections import defaultdict

from aerofleet_opt.evaluate import Placement, Plan
from aerofleet_opt.options import Option, enumerate_options, lot_ready_slot
from aerofleet_opt.problem import Job, PartLot, Problem


def due_hours(problem: Problem, job: Job) -> float:
    legs = problem.flown_legs(problem.aircraft_by_id()[job.aircraft_id])
    if job.threshold_leg is None or job.threshold_leg >= len(legs):
        return float(problem.horizon_slots)
    return problem.hours(legs[job.threshold_leg].departure)


class _Resources:
    def __init__(self, problem: Problem) -> None:
        self.problem = problem
        self.facilities = problem.facility_by_code()
        self.bays: dict[tuple[str, int], int] = defaultdict(int)
        self.techs: dict[tuple[str, int], int] = defaultdict(int)
        self.left = {lot.id: lot.quantity for lot in problem.lots}

    def fits(self, job: Job, opt: Option) -> bool:
        fac = self.facilities[opt.facility]
        return all(
            self.bays[(opt.facility, s)] + 1 <= fac.bays
            and self.techs[(opt.facility, s)] + job.technicians <= fac.technicians[s]
            for s in range(opt.start, opt.end)
        )

    def lot_for(self, job: Job, opt: Option) -> PartLot | None:
        candidates = [
            lot
            for lot in self.problem.lots
            if lot.part_type == job.part_type
            and self.left[lot.id] > 0
            and lot_ready_slot(lot, opt.facility) <= opt.start
        ]
        candidates.sort(key=lambda lot: (lot.location != opt.facility, lot.ready_slot, lot.id))
        return candidates[0] if candidates else None

    def commit(self, job: Job, opt: Option, lot: PartLot | None) -> None:
        for s in range(opt.start, opt.end):
            self.bays[(opt.facility, s)] += 1
            self.techs[(opt.facility, s)] += job.technicians
        if lot is not None:
            self.left[lot.id] -= 1


def solve_heuristic(problem: Problem) -> Plan:
    resources = _Resources(problem)
    placements: list[Placement] = []
    unscheduled: list[str] = []
    for job in sorted(problem.jobs, key=lambda j: (due_hours(problem, j), j.id)):
        options = sorted(enumerate_options(problem, job), key=lambda o: (o.start, o.facility))
        chosen: Placement | None = None
        for opt in options:
            if problem.threshold_policy == "hard" and opt.cycles_over > 0:
                continue
            if not resources.fits(job, opt):
                continue
            lot = resources.lot_for(job, opt) if job.part_type else None
            if job.part_type and lot is None:
                continue
            resources.commit(job, opt, lot)
            chosen = Placement(job.id, opt, lot.id if lot else None)
            break
        if chosen is None:
            unscheduled.append(job.id)
        else:
            placements.append(chosen)
    return Plan(tuple(placements), tuple(sorted(unscheduled)))
