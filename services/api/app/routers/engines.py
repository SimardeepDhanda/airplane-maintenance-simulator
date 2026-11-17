from typing import Annotated, Literal

from fastapi import APIRouter, Query
from sqlalchemy import select

from app import models
from app.deps import BufferDep, SessionDep
from app.errors import ERROR_RESPONSES, not_found
from app.schemas import (
    EngineDetail,
    EngineHistory,
    EngineSummary,
    Page,
    PlanningStatus,
    ProvenanceOut,
    SeriesOut,
)
from app.services.fleet import (
    EngineState,
    active_model,
    flights_out,
    load_snapshot,
    planning_out,
    prediction_out,
)
from app.simulation.seed import SENSORS

router = APIRouter(prefix="/engines", tags=["engines"], responses=ERROR_RESPONSES)

SortKey = Literal["id", "rul_point", "rul_lower", "conservative_margin", "observed_cycles"]
_SORT = {
    "id": lambda s: s.engine.id,
    "rul_point": lambda s: s.prediction.rul_point,
    "rul_lower": lambda s: s.prediction.rul_lower,
    "conservative_margin": lambda s: s.planning.conservative_margin,
    "observed_cycles": lambda s: s.engine.observed_through_cycle,
}


def _summary(state: EngineState) -> EngineSummary:
    return EngineSummary(
        id=state.engine.id,
        aircraft_id=state.aircraft.id if state.aircraft else None,
        station=state.aircraft.initial_station if state.aircraft else None,
        observed_cycles=state.engine.observed_through_cycle,
        prediction=prediction_out(state.prediction),
        planning=planning_out(state.planning),
    )


@router.get("", response_model=Page[EngineSummary])
def list_engines(
    session: SessionDep,
    buffer: BufferDep,
    status: Annotated[list[PlanningStatus] | None, Query()] = None,
    aircraft_id: str | None = None,
    station: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    sort: SortKey = "conservative_margin",
    order: Literal["asc", "desc"] = "asc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[EngineSummary]:
    states = load_snapshot(session, buffer).engines
    if status:
        states = [s for s in states if s.planning.status in status]
    if aircraft_id:
        states = [s for s in states if s.aircraft and s.aircraft.id == aircraft_id]
    if station:
        states = [s for s in states if s.aircraft and s.aircraft.initial_station == station.upper()]
    # Secondary key on id keeps ordering deterministic.
    states.sort(key=lambda s: s.engine.id)
    states.sort(key=_SORT[sort], reverse=order == "desc")
    start = (page - 1) * page_size
    return Page(
        items=[_summary(s) for s in states[start : start + page_size]],
        total=len(states),
        page=page,
        page_size=page_size,
    )


@router.get("/{engine_id}", response_model=EngineDetail)
def get_engine(engine_id: str, session: SessionDep, buffer: BufferDep) -> EngineDetail:
    snap = load_snapshot(session, buffer)
    state = next((s for s in snap.engines if s.engine.id == engine_id), None)
    if state is None:
        raise not_found("engine", engine_id)
    aircraft_flights = (
        [f for f in snap.flights if f.aircraft_id == state.aircraft.id] if state.aircraft else []
    )
    e = state.engine
    return EngineDetail(
        **_summary(state).model_dump(),
        fleet_type=state.aircraft.fleet_type if state.aircraft else None,
        home_base=state.aircraft.home_base if state.aircraft else None,
        provenance=ProvenanceOut(
            dataset=e.source_dataset,
            subset=e.source_subset,
            split=e.source_split,
            unit_id=e.source_unit_id,
            data_kind=snap.model.data_kind,
            eval_true_rul=e.eval_true_rul,
        ),
        flights=flights_out(snap, aircraft_flights),
    )


@router.get("/{engine_id}/history", response_model=EngineHistory)
def engine_history(
    engine_id: str,
    session: SessionDep,
    sensors: Annotated[list[str] | None, Query(description="e.g. sensor_4; default all")] = None,
) -> EngineHistory:
    if session.get(models.Engine, engine_id) is None:
        raise not_found("engine", engine_id)
    wanted = sensors or SENSORS
    unknown = [s for s in wanted if s not in SENSORS]
    if unknown:
        raise not_found("sensor", ", ".join(unknown))
    model = active_model(session)
    observations = list(
        session.scalars(
            select(models.EngineObservation)
            .where(models.EngineObservation.engine_id == engine_id)
            .order_by(models.EngineObservation.cycle)
        )
    )
    predictions = {
        p.cycle: p
        for p in session.scalars(
            select(models.EnginePrediction).where(
                models.EnginePrediction.engine_id == engine_id,
                models.EnginePrediction.model_version == model.version,
            )
        )
    }
    cycles = [o.cycle for o in observations]
    missing = [c for c in cycles if c not in predictions]
    if missing:
        raise not_found("prediction", f"{engine_id} cycle {missing[0]}")
    index = {name: SENSORS.index(name) for name in wanted}
    return EngineHistory(
        engine_id=engine_id,
        model_version=model.version,
        cycles=cycles,
        sensors=[
            SeriesOut(name=name, values=[o.sensors[i] for o in observations])
            for name, i in index.items()
        ],
        rul_point=[predictions[c].rul_point for c in cycles],
        rul_lower=[predictions[c].rul_lower for c in cycles],
        rul_upper=[predictions[c].rul_upper for c in cycles],
    )
