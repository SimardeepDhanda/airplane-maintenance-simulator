from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app import models
from app.deps import SessionDep
from app.errors import ERROR_RESPONSES, APIError, not_found
from app.schemas import (
    PlanOut,
    ScenarioAssumptions,
    ScenarioCreate,
    ScenarioOut,
    ScenarioSummaryOut,
)
from app.services import maintenance

router = APIRouter(
    prefix="/scenarios",
    tags=["scenarios"],
    responses={**ERROR_RESPONSES, 409: ERROR_RESPONSES[422]},
)


def describe(a: ScenarioAssumptions) -> str:
    parts = [f"Buffer {a.buffer}"]
    if a.threshold_policy == "hard":
        parts.append("hard threshold")
    parts += [f"{code} {delta:+d} bay" for code, delta in sorted(a.bay_changes.items()) if delta]
    if a.part_delay_hours:
        parts.append(f"parts +{a.part_delay_hours} h")
    parts += [f"{ship} grounded" for ship in a.grounded_aircraft]
    parts += [f"+{j.job_type.replace('_', ' ')} {j.aircraft_id}" for j in a.added_jobs]
    return " · ".join(parts)[:80]


def _out(session: Session, s: models.Scenario) -> ScenarioOut:
    results = {
        r.method: PlanOut.model_validate(r.result)
        for r in session.scalars(
            select(models.ScenarioResult).where(models.ScenarioResult.scenario_id == s.id)
        )
    }
    baseline, optimized = results.get("baseline"), results.get("optimized")
    return ScenarioOut(
        id=s.id,
        name=s.name,
        status=s.status,
        error=s.error,
        created_at=s.created_at,
        updated_at=s.updated_at,
        assumptions=ScenarioAssumptions.model_validate(s.assumptions),
        baseline=baseline,
        optimized=optimized,
        comparison=maintenance.comparison(baseline, optimized) if results else [],
    )


def _get(session: Session, scenario_id: int) -> models.Scenario:
    s = session.get(models.Scenario, scenario_id)
    if s is None:
        raise not_found("scenario", str(scenario_id))
    return s


@router.get("", response_model=list[ScenarioSummaryOut])
def list_scenarios(
    session: SessionDep, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> list[ScenarioSummaryOut]:
    rows = session.scalars(
        select(models.Scenario).order_by(models.Scenario.id.desc()).limit(limit)
    ).all()
    statuses: dict[tuple[int, str], str] = {
        (r.scenario_id, r.method): r.status
        for r in session.scalars(
            select(models.ScenarioResult).where(
                models.ScenarioResult.scenario_id.in_([s.id for s in rows])
            )
        )
    }
    return [
        ScenarioSummaryOut(
            id=s.id,
            name=s.name,
            status=s.status,
            created_at=s.created_at,
            baseline_status=statuses.get((s.id, "baseline")),
            optimized_status=statuses.get((s.id, "optimized")),
        )
        for s in rows
    ]


@router.post("", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED)
def create_scenario(body: ScenarioCreate, session: SessionDep) -> ScenarioOut:
    """Validate assumptions against the seeded fleet and store them. Does not solve."""
    maintenance.build_problem(session, body.assumptions)  # raises 422 with a specific code
    now = maintenance.now()
    s = models.Scenario(
        name=body.name or describe(body.assumptions),
        assumptions=body.assumptions.model_dump(mode="json"),
        status="created",
        created_at=now,
        updated_at=now,
    )
    session.add(s)
    session.commit()
    return _out(session, s)


@router.get("/{scenario_id}", response_model=ScenarioOut)
def get_scenario(scenario_id: int, session: SessionDep) -> ScenarioOut:
    return _out(session, _get(session, scenario_id))


@router.post(
    "/{scenario_id}/solve", response_model=ScenarioOut, status_code=status.HTTP_202_ACCEPTED
)
def solve_scenario(
    scenario_id: int, session: SessionDep, background: BackgroundTasks, request: Request
) -> ScenarioOut:
    """Queue the baseline and CP-SAT runs. Poll GET /scenarios/{id} until solved or failed."""
    s = _get(session, scenario_id)
    if s.status in ("queued", "running"):
        raise APIError(status.HTTP_409_CONFLICT, "already_running", "Scenario is already solving")
    s.status, s.error, s.updated_at = "queued", None, maintenance.now()
    session.commit()
    background.add_task(run_solve, request.app.state.session_factory, scenario_id)
    return _out(session, s)


INTERRUPTED = "Interrupted: the API restarted while this scenario was solving. Run it again."


def fail_interrupted(factory: sessionmaker[Session]) -> int:
    """Mark solves orphaned by a restart as failed. Solves run in-process, so at startup none can
    still be running. Returns the number of scenarios marked."""
    with factory() as session:
        stuck = session.scalars(
            select(models.Scenario).where(models.Scenario.status.in_(("queued", "running")))
        ).all()
        for s in stuck:
            s.status, s.error, s.updated_at = "failed", INTERRUPTED, maintenance.now()
        session.commit()
        return len(stuck)


def run_solve(factory: sessionmaker[Session], scenario_id: int) -> None:
    with factory() as session:
        s = session.get(models.Scenario, scenario_id)
        if s is None:
            return
        s.status, s.updated_at = "running", maintenance.now()
        session.commit()
        try:
            assumptions = ScenarioAssumptions.model_validate(s.assumptions)
            ctx = maintenance.build_problem(session, assumptions)
            plans = maintenance.solve(ctx, assumptions.time_limit_s)
            for plan in plans:
                row = session.get(models.ScenarioResult, (scenario_id, plan.method))
                if row is None:
                    row = models.ScenarioResult(scenario_id=scenario_id, method=plan.method)
                    session.add(row)
                row.status = plan.status
                row.objective = plan.objective
                row.best_bound = plan.best_bound
                row.wall_ms = plan.wall_ms
                row.result = plan.model_dump(mode="json")
                row.created_at = maintenance.now()
            s.status = "solved"
        except Exception as exc:  # recorded on the scenario, never swallowed silently
            session.rollback()
            s = session.get(models.Scenario, scenario_id)
            if s is None:
                return
            s.status, s.error = "failed", f"{type(exc).__name__}: {exc}"[:500]
        s.updated_at = maintenance.now()
        session.commit()
