"""Enumerate where and when each job can physically happen.

An option is (facility, start slot). The aircraft must be on the ground at the facility's station
when the job starts. If the job runs past the next departure, the aircraft's legs from that
departure are cancelled up to and including the first leg that brings it back to the same station
departing again after the job ends (or to the end of the horizon). The remaining schedule therefore
keeps location continuity without inventing ferry flights.
"""

from __future__ import annotations

from dataclasses import dataclass

from aerofleet_opt.problem import Aircraft, Facility, Job, Leg, PartLot, Problem


@dataclass(frozen=True)
class Option:
    job_id: str
    facility: str
    start: int
    end: int  # exclusive
    legs_flown_before: int  # k: legs[0:k] are flown before the job starts
    cancelled: tuple[str, ...]  # leg ids cancelled to make room (contiguous block from leg k)
    cycles_over: int  # cycles flown past the planning threshold before the job starts
    labor_hours: int  # technician-hours
    labor_cost: int
    on_ground_until: int | None  # slot of the departure that ends the ground window (None: horizon)


def lot_ready_slot(lot: PartLot, facility: str) -> int:
    return lot.ready_slot + (0 if lot.location == facility else lot.transfer_slots)


def cycles_over(job: Job, legs: tuple[Leg, ...], flown_before: int) -> int:
    if job.threshold_leg is None or flown_before <= job.threshold_leg:
        return 0
    return sum(leg.cycles for leg in legs[job.threshold_leg : flown_before])


def unscheduled_cycles_over(problem: Problem, job: Job) -> int:
    aircraft = problem.aircraft_by_id()[job.aircraft_id]
    legs = problem.flown_legs(aircraft)
    return cycles_over(job, legs, len(legs))


def _windows(problem: Problem, aircraft: Aircraft) -> list[tuple[int, str, float, float]]:
    """(legs flown before, station, ground from [h], ground until [h]) for each ground window."""
    legs = problem.flown_legs(aircraft)
    horizon = float(problem.horizon_slots)
    out: list[tuple[int, str, float, float]] = []
    station = aircraft.initial_station
    ready = 0.0
    for k, leg in enumerate(legs):
        out.append((k, station, ready, problem.hours(leg.departure)))
        station, ready = leg.destination, problem.hours(leg.arrival)
    out.append((len(legs), station, ready, horizon))
    return out


def _cancellations(
    legs: tuple[Leg, ...], k: int, station: str, end_hours: float, problem: Problem
) -> tuple[str, ...]:
    for m in range(k, len(legs)):
        if legs[m].destination != station:
            continue
        nxt = legs[m + 1] if m + 1 < len(legs) else None
        if nxt is None or problem.hours(nxt.departure) >= end_hours:
            return tuple(leg.id for leg in legs[k : m + 1])
    return tuple(leg.id for leg in legs[k:])


def _labor(job: Job, facility: Facility, start: int, end: int, problem: Problem) -> int:
    w = problem.weights
    return sum(
        job.technicians * (w.tech_hour_night if facility.night[s] else w.tech_hour_day)
        for s in range(start, end)
    )


def enumerate_options(problem: Problem, job: Job) -> list[Option]:
    """All presence-feasible options, ignoring shared resources (bays, technicians, parts)."""
    aircraft = problem.aircraft_by_id()[job.aircraft_id]
    facilities = problem.facility_by_code()
    legs = problem.flown_legs(aircraft)
    options: list[Option] = []
    last_start = problem.horizon_slots - job.duration_slots
    for k, station, ground_from, ground_until in _windows(problem, aircraft):
        facility = facilities.get(station)
        if facility is None or job.job_type not in facility.supports:
            continue
        first = max(0, _ceil(ground_from))
        for start in range(first, last_start + 1):
            if start >= ground_until:  # aircraft has departed
                break
            end = start + job.duration_slots
            cancelled = (
                () if end <= ground_until else _cancellations(legs, k, station, end, problem)
            )
            options.append(
                Option(
                    job_id=job.id,
                    facility=station,
                    start=start,
                    end=end,
                    legs_flown_before=k,
                    cancelled=cancelled,
                    cycles_over=cycles_over(job, legs, k),
                    labor_hours=job.technicians * job.duration_slots,
                    labor_cost=_labor(job, facility, start, end, problem),
                    on_ground_until=None if k >= len(legs) else _ceil(ground_until),
                )
            )
    return options


def _ceil(hours: float) -> int:
    whole = int(hours)
    return whole if hours - whole <= 1e-9 else whole + 1
