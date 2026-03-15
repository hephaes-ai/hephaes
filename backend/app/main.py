"""FastAPI application entrypoint for the local backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.assets import router as assets_router
from backend.app.api.health import router as health_router
from backend.app.config import get_settings
from backend.app.db.session import create_engine_and_session_factory, initialize_database


def create_app() -> FastAPI:
    settings = get_settings()
    engine, session_factory = create_engine_and_session_factory(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        initialize_database(engine)
        app.state.engine = engine
        app.state.session_factory = session_factory
        yield
        engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.include_router(health_router)
    app.include_router(assets_router)
    return app


app = create_app()
