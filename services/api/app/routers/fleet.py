from fastapi import APIRouter

from app.deps import BufferDep, SessionDep
from app.errors import ERROR_RESPONSES
from app.schemas import FleetSummary, ModelRef, StatusCounts
from app.services.fleet import load_snapshot

router = APIRouter(prefix="/fleet", tags=["fleet"], responses=ERROR_RESPONSES)


@router.get("/summary", response_model=FleetSummary)
def fleet_summary(session: SessionDep, buffer: BufferDep) -> FleetSummary:
    snap = load_snapshot(session, buffer)
    counts = {"ok": 0, "review": 0, "critical": 0}
    for state in snap.engines:
        counts[state.planning.status] += 1
    return FleetSummary(
        as_of=snap.simulation.starts_at,
        horizon_end=snap.simulation.ends_at,
        aircraft=len({s.aircraft.id for s in snap.engines if s.aircraft}),
        engines=len(snap.engines),
        flights=len(snap.flights),
        planning_buffer=buffer,
        status_counts=StatusCounts(**counts),
        model=ModelRef(
            version=snap.model.version,
            data_kind=snap.model.data_kind,
            subset=snap.model.subset,
            trained_at=snap.model.trained_at,
        ),
    )
