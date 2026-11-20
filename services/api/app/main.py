"""Application factory. Serve with `uvicorn --factory app.main:create_app`."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app.config import Settings, get_settings
from app.db import build_engine, build_session_factory
from app.errors import install_error_handlers
from app.routers import engines, fleet, flights, health, maintenance, reference, scenarios

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    engine = build_engine(resolved)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            marked = scenarios.fail_interrupted(app.state.session_factory)
            if marked:
                log.warning("marked %d interrupted scenario solve(s) as failed", marked)
        except SQLAlchemyError:
            # Start anyway: /health reports the database as unavailable.
            log.warning("database unavailable at startup; skipped interrupted-solve cleanup")
        yield
        engine.dispose()

    app = FastAPI(title="AeroFleet API", version=__version__, lifespan=lifespan)
    app.state.settings = resolved
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)

    # The flight list is ~270 KB of JSON; gzip brings it to a few tens of KB.
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    if resolved.cors_origins or resolved.cors_origin_regex:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved.cors_origins,
            allow_origin_regex=resolved.cors_origin_regex,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    install_error_handlers(app)
    app.include_router(health.router)
    v1 = APIRouter(prefix="/api/v1")
    for module in (fleet, engines, flights, maintenance, scenarios, reference):
        v1.include_router(module.router)
    app.include_router(v1)
    return app
