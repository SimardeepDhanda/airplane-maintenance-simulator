from fastapi import APIRouter
from sqlalchemy import select

from app import models
from app.deps import SessionDep
from app.errors import ERROR_RESPONSES
from app.schemas import AirportOut, ModelMetrics, ModelRef
from app.services.fleet import active_model

router = APIRouter(tags=["reference"], responses=ERROR_RESPONSES)


@router.get("/airports", response_model=list[AirportOut])
def list_airports(session: SessionDep) -> list[AirportOut]:
    rows = session.scalars(select(models.Airport).order_by(models.Airport.code))
    return [AirportOut.model_validate(a, from_attributes=True) for a in rows]


@router.get("/models/metrics", response_model=ModelMetrics)
def model_metrics(session: SessionDep) -> ModelMetrics:
    """Measured evaluation results of the active model, exactly as written by the pipeline."""
    m = active_model(session)
    return ModelMetrics(
        model=ModelRef(
            version=m.version, data_kind=m.data_kind, subset=m.subset, trained_at=m.trained_at
        ),
        selection=m.metrics["selection"],
        test=m.metrics["test"],
        permutation_importance=m.metrics["permutation_importance"],
        features=m.manifest["features"],
        conformal=m.manifest["conformal"],
        split=m.manifest["split"],
    )
