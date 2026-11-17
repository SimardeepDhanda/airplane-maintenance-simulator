from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import SessionDep
from app.errors import ERROR_RESPONSES
from app.schemas import MaintenanceResources, PlanOut
from app.services import maintenance

router = APIRouter(prefix="/maintenance", tags=["maintenance"], responses=ERROR_RESPONSES)


@router.get("/resources", response_model=MaintenanceResources)
def get_resources(session: SessionDep) -> MaintenanceResources:
    """Facilities, bays, technician rosters (local time), spare-part lots and job types."""
    return maintenance.resources(session)


@router.get("/plan", response_model=PlanOut)
def get_plan(
    session: SessionDep,
    buffer: Annotated[
        int | None,
        Query(ge=0, le=200, description="Re-derive job cards at this buffer (default: seeded)"),
    ] = None,
) -> PlanOut:
    """Job cards placed by the transparent baseline (earliest due date, first feasible slot).

    Without `buffer`: the seeded open job cards. Run a scenario for the CP-SAT optimizer.
    """
    return maintenance.baseline_plan(session, buffer)
