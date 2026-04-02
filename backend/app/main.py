"""FastAPI application entrypoint for the local backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.assets import router as assets_router
from app.api.conversion_configs import router as conversion_configs_router
from app.api.conversions import router as conversions_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.outputs import router as outputs_router
from app.api.tags import router as tags_router
from app.config import get_settings
from app.services.job_runner import BackendJobRunner
from app.workspace_bootstrap import bootstrap_workspace_registry, resolve_backend_workspace


def create_app() -> FastAPI:
    settings = get_settings()
    job_runner = BackendJobRunner(
        max_workers=settings.job_max_workers,
        inline=settings.job_execution_mode == "inline",
    )
    workspace_registry = bootstrap_workspace_registry(settings)
    workspace = resolve_backend_workspace(settings, workspace_registry)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.app_db_path.parent.mkdir(parents=True, exist_ok=True)
        settings.workspace_root.mkdir(parents=True, exist_ok=True)
        settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
        settings.outputs_dir.mkdir(parents=True, exist_ok=True)
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        app.state.job_runner = job_runner
        app.state.workspace_registry = workspace_registry
        app.state.workspace = workspace
        yield
        job_runner.shutdown()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=settings.cors_allow_origin_regex,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.include_router(health_router)
    app.include_router(assets_router)
    app.include_router(dashboard_router)
    app.include_router(conversion_configs_router)
    app.include_router(conversions_router)
    app.include_router(jobs_router)
    app.include_router(outputs_router)
    app.include_router(tags_router)

    return app


app = create_app()
