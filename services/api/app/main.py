"""Application factory. Serve with `uvicorn --factory app.main:create_app`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import Settings, get_settings
from app.db import build_engine, build_session_factory
from app.errors import install_error_handlers
from app.routers import engines, fleet, flights, health, reference


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    engine = build_engine(resolved)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(title="AeroFleet API", version=__version__, lifespan=lifespan)
    app.state.settings = resolved
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)

    if resolved.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved.cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    install_error_handlers(app)
    app.include_router(health.router)
    v1 = APIRouter(prefix="/api/v1")
    for module in (fleet, engines, flights, reference):
        v1.include_router(module.router)
    app.include_router(v1)
    return app
