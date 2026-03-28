"""Visualization preparation and viewer-source routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api._status import HTTP_422_UNPROCESSABLE_CONTENT
from app.dependencies import get_db_session, get_workspace
from app.schemas.jobs import JobResponse
from app.schemas.visualization import (
    PrepareVisualizationResponse,
    ViewerSourceResponse,
)
from app.services.assets import AssetNotFoundError, EpisodeDiscoveryUnavailableError
from app.services.episodes import EpisodeNotFoundError, EpisodePlaybackError
from app.services.visualization import (
    VisualizationError,
    VisualizationGenerationError,
    VisualizationService,
    run_visualization_job_in_background,
)
from app.services.jobs import get_job_or_raise
from hephaes import Workspace

router = APIRouter(
    prefix="/assets/{asset_id}/episodes/{episode_id}",
    tags=["visualization"],
)
DbSession = Annotated[Session, Depends(get_db_session)]
WorkspaceDep = Annotated[Workspace, Depends(get_workspace)]


@router.post("/prepare-visualization", response_model=PrepareVisualizationResponse)
def prepare_visualization_route(
    asset_id: str,
    episode_id: str,
    request: Request,
    session: DbSession,
    workspace: WorkspaceDep,
) -> PrepareVisualizationResponse:
    try:
        service = VisualizationService(session, workspace)
        job, execution = service.prepare_visualization_job(asset_id, episode_id)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EpisodeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EpisodeDiscoveryUnavailableError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except EpisodePlaybackError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except VisualizationGenerationError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except VisualizationError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    if execution is not None:
        try:
            request.app.state.job_runner.submit(
                f"prepare visualization for {asset_id}:{episode_id}",
                run_visualization_job_in_background,
                request.app.state.session_factory,
                execution=execution,
            )
        except VisualizationGenerationError as exc:
            raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        except VisualizationError as exc:
            raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    session.expire_all()
    job = get_job_or_raise(session, job.id)
    return PrepareVisualizationResponse(job=JobResponse.model_validate(job, from_attributes=True))


@router.get("/viewer-source", response_model=ViewerSourceResponse)
def get_viewer_source_route(
    asset_id: str,
    episode_id: str,
    session: DbSession,
    workspace: WorkspaceDep,
) -> ViewerSourceResponse:
    try:
        service = VisualizationService(session, workspace)
        manifest = service.get_viewer_source(asset_id, episode_id)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EpisodeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EpisodeDiscoveryUnavailableError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return ViewerSourceResponse(
        episode_id=manifest.episode_id,
        status=manifest.status,
        source_kind=manifest.source_kind,
        source_url=manifest.source_url,
        job_id=manifest.job_id,
        artifact_path=manifest.artifact_path,
        error_message=manifest.error_message,
        viewer_version=manifest.viewer_version,
        recording_version=manifest.recording_version,
        updated_at=manifest.updated_at,
    )
