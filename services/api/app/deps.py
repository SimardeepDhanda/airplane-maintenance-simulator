from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from app.config import Settings


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def planning_buffer(
    settings: Annotated[Settings, Depends(get_app_settings)],
    buffer: Annotated[
        int | None,
        Query(ge=0, le=200, description="Planning buffer in cycles (hypothetical policy)"),
    ] = None,
) -> int:
    return settings.planning_buffer_cycles if buffer is None else buffer


SessionDep = Annotated[Session, Depends(get_session)]
BufferDep = Annotated[int, Depends(planning_buffer)]
