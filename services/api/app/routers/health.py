from fastapi import APIRouter, Request, Response, status
from sqlalchemy import Engine

from app import __version__
from app.db import database_is_reachable
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
def health(request: Request, response: Response) -> HealthResponse:
    engine: Engine = request.app.state.engine
    if database_is_reachable(engine):
        return HealthResponse(status="ok", database="ok", version=__version__)
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status="degraded", database="unavailable", version=__version__)
