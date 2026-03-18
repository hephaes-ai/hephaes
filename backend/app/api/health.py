"""Health-check routes for the backend app."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.config import Settings

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    if not isinstance(settings, Settings):
        raise RuntimeError("application settings are not configured")

    return {
        "status": "ok",
        "app_name": settings.app_name,
    }
