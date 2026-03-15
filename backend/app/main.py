"""FastAPI application entrypoint for the local backend."""

from __future__ import annotations

from fastapi import FastAPI

from backend.app.api.health import router as health_router
from backend.app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
    )
    app.state.settings = settings
    app.include_router(health_router)
    return app


app = create_app()
