from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import BufferDep, SessionDep
from app.errors import ERROR_RESPONSES, APIError
from app.schemas import FlightOut, Page
from app.services.fleet import flights_out, load_snapshot

router = APIRouter(prefix="/flights", tags=["flights"], responses=ERROR_RESPONSES)


@router.get("", response_model=Page[FlightOut])
def list_flights(
    session: SessionDep,
    buffer: BufferDep,
    aircraft_id: str | None = None,
    engine_id: str | None = None,
    origin: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    destination: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    departure_from: Annotated[datetime | None, Query(description="UTC, inclusive")] = None,
    departure_to: Annotated[datetime | None, Query(description="UTC, exclusive")] = None,
    flagged: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Page[FlightOut]:
    for name, value in (("departure_from", departure_from), ("departure_to", departure_to)):
        if value is not None and value.tzinfo is None:
            raise APIError(422, "naive_datetime", f"{name} must include a UTC offset")
    snap = load_snapshot(session, buffer)
    selected = snap.flights
    if engine_id:
        aircraft = next(
            (s.aircraft.id for s in snap.engines if s.engine.id == engine_id and s.aircraft), None
        )
        selected = [f for f in selected if f.aircraft_id == aircraft]
    if aircraft_id:
        selected = [f for f in selected if f.aircraft_id == aircraft_id]
    if origin:
        selected = [f for f in selected if f.origin == origin.upper()]
    if destination:
        selected = [f for f in selected if f.destination == destination.upper()]
    if departure_from:
        selected = [f for f in selected if f.scheduled_departure >= departure_from]
    if departure_to:
        selected = [f for f in selected if f.scheduled_departure < departure_to]
    annotated = flights_out(snap, selected)
    if flagged is not None:
        annotated = [f for f in annotated if f.flagged == flagged]
    start = (page - 1) * page_size
    return Page(
        items=annotated[start : start + page_size],
        total=len(annotated),
        page=page,
        page_size=page_size,
    )
