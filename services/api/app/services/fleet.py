"""Read-side fleet queries: joins seeded data with planning assessments."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.errors import not_seeded
from app.schemas import FlightOut, PlanningOut, PredictionOut
from app.services.planning import Leg, PlanningAssessment, assess


@dataclass(frozen=True)
class EngineState:
    engine: models.Engine
    aircraft: models.Aircraft | None
    prediction: models.EnginePrediction
    planning: PlanningAssessment


@dataclass(frozen=True)
class Snapshot:
    simulation: models.Simulation
    model: models.ModelVersion
    airports: dict[str, models.Airport]
    engines: list[EngineState]
    flights: list[models.Flight]

    def engine_for_aircraft(self) -> dict[str, EngineState]:
        return {s.aircraft.id: s for s in self.engines if s.aircraft is not None}


def active_model(session: Session) -> models.ModelVersion:
    model = session.scalar(select(models.ModelVersion).where(models.ModelVersion.is_active))
    if model is None:
        raise not_seeded()
    return model


def load_snapshot(session: Session, buffer: int) -> Snapshot:
    simulation = session.get(models.Simulation, 1)
    if simulation is None:
        raise not_seeded()
    model = active_model(session)
    airports = {a.code: a for a in session.scalars(select(models.Airport))}
    flights = list(
        session.scalars(
            select(models.Flight)
            .where(models.Flight.status == "scheduled")
            .where(models.Flight.scheduled_departure >= simulation.starts_at)
            .order_by(models.Flight.scheduled_departure, models.Flight.id)
        )
    )
    legs: dict[str, list[Leg]] = defaultdict(list)
    for f in flights:
        legs[f.aircraft_id].append(Leg(f.id, f.scheduled_departure, f.cycles))

    rows = session.execute(
        select(models.Engine, models.Aircraft, models.EnginePrediction)
        .outerjoin(models.Aircraft, models.Engine.aircraft_id == models.Aircraft.id)
        .join(
            models.EnginePrediction,
            (models.EnginePrediction.engine_id == models.Engine.id)
            & (models.EnginePrediction.cycle == models.Engine.observed_through_cycle)
            & (models.EnginePrediction.model_version == model.version),
        )
        .order_by(models.Engine.id)
    ).all()
    engines = [
        EngineState(
            engine=engine,
            aircraft=aircraft,
            prediction=pred,
            planning=assess(
                pred.rul_point,
                pred.rul_lower,
                legs.get(aircraft.id, []) if aircraft else [],
                buffer,
            ),
        )
        for engine, aircraft, pred in rows
    ]
    return Snapshot(simulation, model, airports, engines, flights)


def prediction_out(p: models.EnginePrediction) -> PredictionOut:
    return PredictionOut(
        rul_point=p.rul_point,
        rul_lower=p.rul_lower,
        rul_upper=p.rul_upper,
        model_version=p.model_version,
        observed_through_cycle=p.cycle,
    )


def planning_out(a: PlanningAssessment) -> PlanningOut:
    return PlanningOut(
        forecast_legs=a.forecast_legs,
        forecast_cycles=a.forecast_cycles,
        margin=round(a.margin, 2),
        conservative_margin=round(a.conservative_margin, 2),
        status=a.status,
        buffer=a.buffer,
        first_flagged_flight_id=a.first_flagged_flight_id,
        first_flagged_departure=a.first_flagged_departure,
    )


def _local(ts: datetime, tz: str) -> tuple[datetime, str]:
    local = ts.astimezone(ZoneInfo(tz))
    return local, local.tzname() or tz


def flights_out(snapshot: Snapshot, flights: Sequence[models.Flight]) -> list[FlightOut]:
    """Annotate flights with cumulative cycles and the engine's conservative margin after each leg.

    Cumulative counts run over each aircraft's full horizon, so they are correct for any subset.
    """
    by_aircraft = snapshot.engine_for_aircraft()
    cumulative: dict[str, int] = {}
    running: dict[str, int] = defaultdict(int)
    for f in snapshot.flights:
        running[f.aircraft_id] += f.cycles
        cumulative[f.id] = running[f.aircraft_id]

    out = []
    for f in flights:
        origin, dest = snapshot.airports[f.origin], snapshot.airports[f.destination]
        dep_local, dep_abbr = _local(f.scheduled_departure, origin.timezone)
        arr_local, arr_abbr = _local(f.scheduled_arrival, dest.timezone)
        state = by_aircraft.get(f.aircraft_id)
        cum = cumulative.get(f.id, 0)
        after = round(state.prediction.rul_lower - cum, 2) if state else None
        out.append(
            FlightOut(
                id=f.id,
                flight_number=f.flight_number,
                aircraft_id=f.aircraft_id,
                engine_id=state.engine.id if state else None,
                origin=f.origin,
                destination=f.destination,
                departure=f.scheduled_departure,
                arrival=f.scheduled_arrival,
                departure_local=dep_local,
                arrival_local=arr_local,
                origin_tz=origin.timezone,
                destination_tz=dest.timezone,
                origin_tz_abbr=dep_abbr,
                destination_tz_abbr=arr_abbr,
                status=f.status,
                cycles=f.cycles,
                cumulative_cycles=cum,
                conservative_margin_after=after,
                flagged=state is not None and f.id in state.planning.flagged_flight_ids,
            )
        )
    return out
