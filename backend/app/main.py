"""FastAPI application entrypoint for the local backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles

from app.api.assets import router as assets_router
from app.api.conversion_configs import router as conversion_configs_router
from app.api.conversions import router as conversions_router
from app.api.dashboard import router as dashboard_router
from app.api.episodes import router as episodes_router
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.outputs import output_actions_router, router as outputs_router
from app.api.tags import router as tags_router
from app.api.visualization import router as visualization_router
from app.config import get_settings
from app.db.session import create_engine_and_session_factory, initialize_database
from app.services.job_runner import BackendJobRunner
from hephaes import Workspace, WorkspaceNotFoundError


def create_app() -> FastAPI:
    settings = get_settings()
    engine, session_factory = create_engine_and_session_factory(settings)
    job_runner = BackendJobRunner(
        max_workers=settings.job_max_workers,
        inline=settings.job_execution_mode == "inline",
    )
    try:
        workspace = Workspace.open(settings.workspace_root)
    except WorkspaceNotFoundError:
        workspace = Workspace.init(settings.workspace_root, exist_ok=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.workspace_root.mkdir(parents=True, exist_ok=True)
        settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
        settings.outputs_dir.mkdir(parents=True, exist_ok=True)
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        initialize_database(engine)
        app.state.engine = engine
        app.state.job_runner = job_runner
        app.state.session_factory = session_factory
        app.state.workspace = workspace
        yield
        job_runner.shutdown()
        engine.dispose()

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
    app.include_router(episodes_router)
    app.include_router(dashboard_router)
    app.include_router(conversion_configs_router)
    app.include_router(conversions_router)
    app.include_router(jobs_router)
    app.include_router(outputs_router)
    app.include_router(output_actions_router)
    app.include_router(tags_router)
    app.include_router(visualization_router)

    visualizations_dir = settings.outputs_dir / "visualizations"
    visualizations_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/visualizations",
        StaticFiles(directory=str(visualizations_dir)),
        name="visualizations",
    )

    return app


app = create_app()
