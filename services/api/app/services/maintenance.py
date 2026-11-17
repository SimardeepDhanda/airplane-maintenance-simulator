"""Build optimizer problems from the seeded database and turn results into API models.

Jobs: every engine whose planning status is not `ok` gets a job card (critical -> engine change,
review -> borescope). Its threshold is the first flagged leg: flying that leg before the job counts
as cycles over the planning threshold.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from aerofleet_opt.compare import MethodResult, percent_change, run_baseline, run_optimizer
from aerofleet_opt.evaluate import Placement
from aerofleet_opt.options import unscheduled_cycles_over
from aerofleet_opt.problem import Aircraft, Facility, Job, Leg, PartLot, Problem
from app import models
from app.errors import APIError
from app.schemas import (
    BayOut,
    ComparisonRow,
    CostsOut,
    ExplanationOut,
    FacilityOut,
    JobOut,
    JobType,
    JobTypeOut,
    MaintenanceResources,
    PartLotOut,
    PlacementOut,
    PlanMetricsOut,
    PlanOut,
    ScenarioAssumptions,
    ShiftOut,
    UnscheduledOut,
)
from app.services.fleet import Snapshot, load_snapshot
from app.simulation.maintenance import JOB_FOR_STATUS, JOB_TYPES, ShiftSpec, roster


def _invalid(code: str, message: str) -> APIError:
    return APIError(422, code, message)


@dataclass(frozen=True)
class Context:
    """Lookup data needed to present a result."""

    snapshot: Snapshot
    problem: Problem
    jobs: list[JobOut]
    bays: dict[str, list[str]]  # facility -> bay ids
    timezones: dict[str, str]  # facility -> tz
    lot_location: dict[str, str]


def _facility_rows(session: Session) -> list[models.MaintenanceFacility]:
    return list(
        session.scalars(
            select(models.MaintenanceFacility).order_by(models.MaintenanceFacility.code)
        )
    )


def _shifts(session: Session) -> dict[str, list[models.TechnicianShift]]:
    out: dict[str, list[models.TechnicianShift]] = defaultdict(list)
    for s in session.scalars(select(models.TechnicianShift).order_by(models.TechnicianShift.id)):
        out[s.facility_code].append(s)
    return out


def _bays(session: Session) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for b in session.scalars(select(models.MaintenanceBay).order_by(models.MaintenanceBay.id)):
        out[b.facility_code].append(b.id)
    return out


def resources(session: Session) -> MaintenanceResources:
    snapshot = load_snapshot(session, 0)
    shifts = _shifts(session)
    bays = _bays(session)
    facilities = [
        FacilityOut(
            code=f.code,
            name=f.name,
            kind=cast(Any, f.kind),
            timezone=snapshot.airports[f.code].timezone,
            supports=cast(list[JobType], f.supports),
            bays=[BayOut(id=b, name=b.split("-")[-1]) for b in bays[f.code]],
            shifts=[
                ShiftOut(
                    name=s.name,
                    start_local=s.start_local,
                    end_local=s.end_local,
                    technicians=s.technicians,
                    is_night=s.is_night,
                )
                for s in shifts[f.code]
            ],
        )
        for f in _facility_rows(session)
    ]
    parts = [
        PartLotOut.model_validate(p, from_attributes=True)
        for p in session.scalars(select(models.PartInventory).order_by(models.PartInventory.id))
    ]
    return MaintenanceResources(
        horizon_start=snapshot.simulation.starts_at,
        horizon_end=snapshot.simulation.ends_at,
        facilities=facilities,
        parts=parts,
        job_types=[
            JobTypeOut(
                id=cast(JobType, k),
                label=v.label,
                duration_hours=v.duration_hours,
                technicians=v.technicians,
                part_type=v.part_type,
            )
            for k, v in JOB_TYPES.items()
        ],
    )


def derive_jobs(snapshot: Snapshot) -> list[JobOut]:
    """Job cards for engines flagged under the snapshot's buffer."""
    flights = {f.id: f for f in snapshot.flights}
    out: list[JobOut] = []
    for state in snapshot.engines:
        if state.aircraft is None or state.planning.status == "ok":
            continue
        job_type = JOB_FOR_STATUS[state.planning.status]
        spec = JOB_TYPES[job_type]
        due = state.planning.first_flagged_flight_id
        out.append(
            JobOut(
                id=f"MX-{state.engine.id}",
                engine_id=state.engine.id,
                aircraft_id=state.aircraft.id,
                job_type=cast(JobType, job_type),
                reason=state.planning.status,
                duration_hours=spec.duration_hours,
                technicians=spec.technicians,
                part_type=spec.part_type,
                due_flight_id=due,
                due_at=flights[due].scheduled_departure if due else None,
            )
        )
    return out


def seeded_jobs(session: Session) -> list[JobOut]:
    rows = session.scalars(
        select(models.MaintenanceJob)
        .where(models.MaintenanceJob.status == "open")
        .order_by(models.MaintenanceJob.id)
    )
    return [
        JobOut(
            id=r.id,
            engine_id=r.engine_id,
            aircraft_id=r.aircraft_id,
            job_type=cast(JobType, r.job_type),
            reason=cast(Any, r.reason),
            duration_hours=r.duration_hours,
            technicians=r.technicians,
            part_type=r.part_type,
            due_flight_id=r.due_flight_id,
            due_at=r.due_at,
        )
        for r in rows
    ]


def _validate(a: ScenarioAssumptions, snapshot: Snapshot, facilities: dict[str, int]) -> None:
    for code, delta in a.bay_changes.items():
        if code not in facilities:
            raise _invalid("unknown_facility", f"No maintenance facility '{code}'")
        if not -facilities[code] <= delta <= 3:
            raise _invalid(
                "invalid_bay_change",
                f"{code} has {facilities[code]} bays; change must be between "
                f"-{facilities[code]} and +3",
            )
    ships = {s.aircraft.id for s in snapshot.engines if s.aircraft is not None}
    for ship in [*a.grounded_aircraft, *(j.aircraft_id for j in a.added_jobs)]:
        if ship not in ships:
            raise _invalid("unknown_aircraft", f"No aircraft '{ship}'")
    if len(set(a.grounded_aircraft)) != len(a.grounded_aircraft):
        raise _invalid("duplicate_aircraft", "Aircraft listed twice in grounded_aircraft")


def build_problem(
    session: Session, assumptions: ScenarioAssumptions, jobs: list[JobOut] | None = None
) -> Context:
    snapshot = load_snapshot(session, assumptions.buffer)
    facility_rows = _facility_rows(session)
    bays = _bays(session)
    _validate(assumptions, snapshot, {f.code: len(bays[f.code]) for f in facility_rows})

    start = snapshot.simulation.starts_at
    horizon = round((snapshot.simulation.ends_at - start) / timedelta(hours=1))

    legs: dict[str, list[Leg]] = defaultdict(list)
    for f in snapshot.flights:
        legs[f.aircraft_id].append(
            Leg(
                f.id,
                f.flight_number,
                f.origin,
                f.destination,
                f.scheduled_departure,
                f.scheduled_arrival,
                f.cycles,
            )
        )
    grounded = set(assumptions.grounded_aircraft)
    aircraft = tuple(
        Aircraft(
            s.aircraft.id,
            s.aircraft.initial_station,
            tuple(legs[s.aircraft.id]),
            s.aircraft.id in grounded,
        )
        for s in snapshot.engines
        if s.aircraft is not None
    )

    shifts = _shifts(session)
    timezones = {f.code: snapshot.airports[f.code].timezone for f in facility_rows}
    facilities = []
    for fr in facility_rows:
        specs = tuple(
            ShiftSpec(s.name, s.start_local, s.end_local, s.technicians, s.is_night)
            for s in shifts[fr.code]
        )
        techs, night = roster(specs, timezones[fr.code], start, horizon)
        facilities.append(
            Facility(
                fr.code,
                fr.name,
                len(bays[fr.code]) + assumptions.bay_changes.get(fr.code, 0),
                frozenset(fr.supports),
                techs,
                night,
            )
        )

    lots = []
    delay = timedelta(hours=assumptions.part_delay_hours)
    for p in session.scalars(select(models.PartInventory).order_by(models.PartInventory.id)):
        ready = p.available_at + delay if p.available_at > start else p.available_at
        lots.append(
            PartLot(
                p.id,
                p.part_type,
                p.location,
                p.quantity,
                max(0, -int(-(ready - start) // timedelta(hours=1))),
                p.transfer_lead_hours,
            )
        )

    job_cards = list(jobs) if jobs is not None else derive_jobs(snapshot)
    taken = {j.aircraft_id for j in job_cards}
    for added in assumptions.added_jobs:
        if added.aircraft_id in taken:
            raise _invalid(
                "duplicate_job", f"Aircraft {added.aircraft_id} already has a maintenance job"
            )
        taken.add(added.aircraft_id)
        spec = JOB_TYPES[added.job_type]
        engine = next(
            (
                s.engine.id
                for s in snapshot.engines
                if s.aircraft and s.aircraft.id == added.aircraft_id
            ),
            None,
        )
        job_cards.append(
            JobOut(
                id=f"MX-ADD-{added.aircraft_id}",
                engine_id=engine,
                aircraft_id=added.aircraft_id,
                job_type=added.job_type,
                reason="added",
                duration_hours=spec.duration_hours,
                technicians=spec.technicians,
                part_type=spec.part_type,
                due_flight_id=None,
                due_at=None,
            )
        )

    leg_index = {leg.id: i for ac in aircraft for i, leg in enumerate(legs[ac.id])}
    problem_jobs = tuple(
        Job(
            j.id,
            j.aircraft_id,
            j.engine_id,
            j.job_type,
            j.duration_hours,
            j.technicians,
            j.part_type,
            leg_index.get(j.due_flight_id) if j.due_flight_id else None,
            j.reason,
        )
        for j in job_cards
    )
    problem = Problem(
        start=start,
        horizon_slots=horizon,
        aircraft=aircraft,
        facilities=tuple(facilities),
        lots=tuple(lots),
        jobs=problem_jobs,
        threshold_policy=assumptions.threshold_policy,
    )
    return Context(
        snapshot,
        problem,
        job_cards,
        bays,
        timezones,
        {p.id: p.location for p in problem.lots},
    )


def _assign_bays(ctx: Context, placements: tuple[Placement, ...]) -> dict[str, str]:
    """Interval colouring per facility; always succeeds when bay capacity is respected."""
    out: dict[str, str] = {}
    by_fac: dict[str, list[Placement]] = defaultdict(list)
    for p in placements:
        by_fac[p.option.facility].append(p)
    for code, items in by_fac.items():
        names = ctx.bays.get(code, [])
        free_at: list[int] = []
        for p in sorted(items, key=lambda x: (x.option.start, x.job_id)):
            idx = next((i for i, t in enumerate(free_at) if t <= p.option.start), None)
            if idx is None:
                free_at.append(p.option.end)
                idx = len(free_at) - 1
            else:
                free_at[idx] = p.option.end
            out[p.job_id] = names[idx] if idx < len(names) else f"{code}-{idx + 1}"
    return out


def plan_out(ctx: Context, result: MethodResult) -> PlanOut:
    problem = ctx.problem
    jobs = {j.id: j for j in ctx.jobs}
    placements: list[PlacementOut] = []
    unscheduled: list[UnscheduledOut] = []
    if result.plan is not None:
        bays = _assign_bays(ctx, result.plan.placements)
        for p in sorted(result.plan.placements, key=lambda x: (x.option.start, x.job_id)):
            j = jobs[p.job_id]
            tz = ZoneInfo(ctx.timezones[p.option.facility])
            start, end = problem.time_of(p.option.start), problem.time_of(p.option.end)
            start_local = start.astimezone(tz)
            placements.append(
                PlacementOut(
                    job_id=j.id,
                    engine_id=j.engine_id,
                    aircraft_id=j.aircraft_id,
                    job_type=j.job_type,
                    reason=j.reason,
                    facility=p.option.facility,
                    bay=bays[p.job_id],
                    start=start,
                    end=end,
                    start_local=start_local,
                    end_local=end.astimezone(tz),
                    tz_abbr=start_local.tzname() or "",
                    cancelled_flights=list(p.option.cancelled),
                    cycles_over=p.option.cycles_over,
                    part_lot=p.lot_id,
                    part_from=ctx.lot_location.get(p.lot_id) if p.lot_id else None,
                    labor_hours=p.option.labor_hours,
                    why=result.reasons.get(p.job_id, []),
                )
            )
        problem_jobs = {j.id: j for j in problem.jobs}
        for job_id in result.plan.unscheduled:
            j = jobs[job_id]
            unscheduled.append(
                UnscheduledOut(
                    job_id=j.id,
                    engine_id=j.engine_id,
                    aircraft_id=j.aircraft_id,
                    job_type=j.job_type,
                    reason=j.reason,
                    cycles_over=unscheduled_cycles_over(problem, problem_jobs[job_id]),
                    why=" ".join(result.reasons.get(job_id, [])),
                )
            )
    c, m = result.costs, result.metrics
    return PlanOut(
        method=result.method,
        status=result.status,
        objective=result.objective,
        best_bound=result.best_bound,
        wall_ms=result.wall_ms,
        costs=CostsOut(
            cancellations=c.cancellations,
            threshold=c.threshold,
            unscheduled=c.unscheduled,
            labor=c.labor,
            transfers=c.transfers,
            total=c.total,
        )
        if c
        else None,
        metrics=PlanMetricsOut(**m.__dict__) if m else None,
        placements=placements,
        unscheduled=unscheduled,
        explanations=[
            ExplanationOut(job_id=e.job_id, code=e.code, message=e.message)
            for e in result.explanations
        ],
        verified=result.plan is not None and not result.violations,
        jobs=ctx.jobs,
    )


def baseline_plan(session: Session, buffer: int | None) -> PlanOut:
    """Job cards placed by the EDD baseline (default resources, penalty policy).

    buffer None: the seeded open job cards; otherwise cards re-derived at that buffer.
    """
    if buffer is None:
        jobs = seeded_jobs(session)
        seeded_buffer = session.scalar(select(models.MaintenanceJob.planning_buffer).limit(1))
        assumptions = ScenarioAssumptions(buffer=seeded_buffer or 0)
        ctx = build_problem(session, assumptions, jobs=jobs)
    else:
        ctx = build_problem(session, ScenarioAssumptions(buffer=buffer))
    return plan_out(ctx, run_baseline(ctx.problem))


def solve(ctx: Context, time_limit_s: float) -> tuple[PlanOut, PlanOut]:
    return plan_out(ctx, run_baseline(ctx.problem)), plan_out(
        ctx, run_optimizer(ctx.problem, time_limit_s)
    )


_ROWS: tuple[tuple[str, str, str, str | None], ...] = (
    ("jobs_scheduled", "Jobs placed", "jobs", "higher"),
    ("thresholds_missed", "Thresholds missed", "jobs", "lower"),
    ("cycles_over_threshold", "Cycles over threshold", "cyc", "lower"),
    ("cancelled_legs", "Cancelled legs", "legs", "lower"),
    ("part_transfers", "Part transfers", "moves", "lower"),
    ("labor_hours", "Technician hours", "h", None),
    ("bay_utilization", "Bay utilisation", "%", None),
    ("total", "Simulated cost", "units", "lower"),
    ("wall_ms", "Compute time", "ms", None),
)


def _value(plan: PlanOut | None, key: str) -> float | None:
    if plan is None or plan.metrics is None or plan.costs is None:
        return None
    if key == "total":
        return float(plan.costs.total)
    if key == "wall_ms":
        return float(plan.wall_ms)
    value = float(getattr(plan.metrics, key))
    return value * 100 if key == "bay_utilization" else value


def comparison(baseline: PlanOut | None, optimized: PlanOut | None) -> list[ComparisonRow]:
    rows = []
    for key, label, unit, better in _ROWS:
        b, o = _value(baseline, key), _value(optimized, key)
        both = b is not None and o is not None
        rows.append(
            ComparisonRow(
                key=key,
                label=label,
                unit=unit,
                baseline=b,
                optimized=o,
                delta=(o - b) if both and o is not None and b is not None else None,
                pct_change=percent_change(b, o)
                if both and o is not None and b is not None
                else None,
                better=cast(Any, better),
            )
        )
    return rows


def now() -> datetime:
    return datetime.now(UTC)
