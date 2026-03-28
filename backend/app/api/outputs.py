"""Output artifact routes for conversion output catalog access."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import ValidationError
from pathlib import Path
from sqlalchemy.orm import Session

from app.api._status import HTTP_422_UNPROCESSABLE_CONTENT
from app.db.session import get_db_session
from app.dependencies import get_workspace
from app.mappers.workspace import map_output_detail
from app.schemas.outputs import (
    OutputActionCreateRequest,
    OutputActionDetailResponse,
    OutputActionSummaryResponse,
    OutputArtifactDetailResponse,
    OutputArtifactSummaryResponse,
    OutputListQueryParams,
)
from app.services.output_actions import (
    OutputActionNotFoundError,
    OutputActionService,
    OutputActionValidationError,
    get_output_action_or_raise,
    list_output_actions_for_output,
)
from app.services.outputs import (
    OutputArtifactContentUnavailableError,
    get_output_artifact,
    get_output_artifact_or_raise,
    OutputArtifactNotFoundError,
    OutputListFilters,
    list_output_artifacts,
    resolve_output_artifact_path,
)
from hephaes import Workspace

router = APIRouter(prefix="/outputs", tags=["outputs"])
output_actions_router = APIRouter(prefix="/output-actions", tags=["outputs"])
DbSession = Annotated[Session, Depends(get_db_session)]
WorkspaceDep = Annotated[Workspace, Depends(get_workspace)]


def parse_list_outputs_query(
    search: Annotated[str | None, Query()] = None,
    format: Annotated[str | None, Query()] = None,
    role: Annotated[str | None, Query()] = None,
    asset_id: Annotated[str | None, Query()] = None,
    conversion_id: Annotated[str | None, Query()] = None,
    availability: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OutputListQueryParams:
    try:
        return OutputListQueryParams.model_validate(
            {
                "search": search,
                "format": format,
                "role": role,
                "asset_id": asset_id,
                "conversion_id": conversion_id,
                "availability": availability,
                "limit": limit,
                "offset": offset,
            }
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(),
        ) from exc


def _content_url_for_output(output_id: str) -> str:
    return f"/outputs/{output_id}/content"


def _output_file_path(artifact) -> str | None:
    if artifact.conversion is None or artifact.conversion.output_path is None:
        return None
    return str(Path(artifact.conversion.output_path) / artifact.relative_path)


def _workspace_output_job_id(workspace: Workspace, artifact) -> str | None:
    if artifact.conversion_run_id is None:
        return None
    run = workspace.get_conversion_run(artifact.conversion_run_id)
    if run is None:
        return None
    return run.job_id


def _workspace_output_summary_response(
    workspace: Workspace,
    artifact,
) -> OutputArtifactSummaryResponse:
    detail = map_output_detail(
        artifact,
        job_id=_workspace_output_job_id(workspace, artifact),
    )
    payload = detail.model_dump()
    payload.pop("file_path", None)
    return OutputArtifactSummaryResponse.model_validate(payload)


def _workspace_output_detail_response(
    workspace: Workspace,
    artifact,
) -> OutputArtifactDetailResponse:
    return map_output_detail(
        artifact,
        job_id=_workspace_output_job_id(workspace, artifact),
    )


def _workspace_output_matches_filters(artifact, query: OutputListQueryParams) -> bool:
    if query.conversion_id is not None and artifact.conversion_run_id != query.conversion_id:
        return False
    if query.asset_id is not None and artifact.source_asset_id != query.asset_id:
        return False
    if query.format is not None and artifact.format.lower() != query.format:
        return False
    if query.role is not None and artifact.role.lower() != query.role:
        return False
    if query.availability is not None and artifact.availability_status.lower() != query.availability:
        return False
    if query.search is not None:
        haystack = " ".join(
            [
                artifact.file_name,
                artifact.relative_path,
                artifact.format,
                artifact.role,
                artifact.conversion_run_id or "",
            ]
        ).lower()
        if query.search.lower() not in haystack:
            return False
    return True


def build_output_action_summary_response(action) -> OutputActionSummaryResponse:
    return OutputActionSummaryResponse(
        id=action.id,
        output_id=action.output_artifact_id,
        action_type=action.action_type,
        status=action.status,
        config=dict(action.config_json),
        result=dict(action.result_json),
        output_path=action.output_path,
        error_message=action.error_message,
        created_at=action.created_at,
        updated_at=action.updated_at,
        started_at=action.started_at,
        finished_at=action.finished_at,
    )


def build_output_summary_response(artifact) -> OutputArtifactSummaryResponse:
    latest_action = artifact.output_actions[0] if artifact.output_actions else None
    return OutputArtifactSummaryResponse(
        id=artifact.id,
        conversion_id=artifact.conversion_id,
        job_id=artifact.job_id,
        asset_ids=list(artifact.source_asset_ids_json),
        relative_path=artifact.relative_path,
        file_name=artifact.file_name,
        format=artifact.format,
        role=artifact.role,
        media_type=artifact.media_type,
        size_bytes=artifact.size_bytes,
        availability_status=artifact.availability_status,
        metadata=dict(artifact.metadata_json),
        latest_action=(
            build_output_action_summary_response(latest_action)
            if latest_action is not None
            else None
        ),
        content_url=_content_url_for_output(artifact.id),
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
    )


@router.get("", response_model=list[OutputArtifactSummaryResponse])
def list_outputs_route(
    workspace: WorkspaceDep,
    session: DbSession,
    query: Annotated[OutputListQueryParams, Depends(parse_list_outputs_query)],
) -> list[OutputArtifactSummaryResponse]:
    full_filters = OutputListFilters(
        search=query.search,
        format=query.format,
        role=query.role,
        asset_id=query.asset_id,
        conversion_id=query.conversion_id,
        availability=query.availability,
        limit=10_000,
        offset=0,
    )
    artifacts = list_output_artifacts(
        session,
        full_filters,
    )
    responses = [build_output_summary_response(artifact) for artifact in artifacts]
    seen_paths = {
        _output_file_path(artifact)
        for artifact in artifacts
        if _output_file_path(artifact) is not None
    }
    for summary in workspace.list_output_artifacts():
        artifact = workspace.get_output_artifact_or_raise(summary.id)
        if not _workspace_output_matches_filters(artifact, query):
            continue
        if artifact.output_path in seen_paths:
            continue
        responses.append(_workspace_output_summary_response(workspace, artifact))

    responses.sort(key=lambda artifact: (artifact.created_at, artifact.id), reverse=True)
    return responses[query.offset : query.offset + query.limit]


@router.get("/{output_id}", response_model=OutputArtifactDetailResponse)
def get_output_route(
    output_id: str,
    workspace: WorkspaceDep,
    session: DbSession,
) -> OutputArtifactDetailResponse:
    artifact = get_output_artifact(session, output_id)
    if artifact is not None:
        return OutputArtifactDetailResponse(
            **build_output_summary_response(artifact).model_dump(),
            file_path=_output_file_path(artifact),
        )

    workspace_artifact = workspace.get_output_artifact(output_id)
    if workspace_artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"output artifact not found: {output_id}",
        )
    return _workspace_output_detail_response(workspace, workspace_artifact)


@router.get("/{output_id}/content")
def get_output_content_route(
    output_id: str,
    workspace: WorkspaceDep,
    session: DbSession,
) -> FileResponse:
    try:
        artifact = get_output_artifact(session, output_id)
        if artifact is not None:
            artifact_path = resolve_output_artifact_path(artifact)
            media_type = artifact.media_type
            file_name = artifact.file_name
        else:
            workspace_artifact = workspace.get_output_artifact(output_id)
            if workspace_artifact is None:
                raise OutputArtifactNotFoundError(f"output artifact not found: {output_id}")
            artifact_path = Path(workspace_artifact.output_path)
            if not artifact_path.exists() or not artifact_path.is_file():
                raise OutputArtifactContentUnavailableError(
                    f"output artifact content is unavailable: {output_id}"
                )
            media_type = workspace_artifact.media_type
            file_name = workspace_artifact.file_name
    except OutputArtifactNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except OutputArtifactContentUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return FileResponse(
        path=str(artifact_path),
        media_type=media_type,
        filename=file_name,
    )


@router.post("/{output_id}/actions", response_model=OutputActionDetailResponse, status_code=status.HTTP_201_CREATED)
def create_output_action_route(
    output_id: str,
    payload: OutputActionCreateRequest,
    session: DbSession,
) -> OutputActionDetailResponse:
    service = OutputActionService(session)

    try:
        action = service.create_action(
            output_id=output_id,
            action_type=payload.action_type,
            config=payload.config,
        )
    except OutputArtifactNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except OutputActionValidationError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    artifact = get_output_artifact_or_raise(session, action.output_artifact_id)
    return OutputActionDetailResponse(
        **build_output_action_summary_response(action).model_dump(),
        output_file_path=_output_file_path(artifact),
    )


@router.get("/{output_id}/actions", response_model=list[OutputActionSummaryResponse])
def list_output_actions_route(output_id: str, session: DbSession) -> list[OutputActionSummaryResponse]:
    try:
        actions = list_output_actions_for_output(session, output_id)
    except OutputArtifactNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return [build_output_action_summary_response(action) for action in actions]


@router.get("/actions/{action_id}", response_model=OutputActionDetailResponse)
def get_output_action_route(action_id: str, session: DbSession) -> OutputActionDetailResponse:
    return _build_output_action_detail_response(action_id, session)


@output_actions_router.get("/{action_id}", response_model=OutputActionDetailResponse)
def get_output_action_route_alias(action_id: str, session: DbSession) -> OutputActionDetailResponse:
    return _build_output_action_detail_response(action_id, session)


def _build_output_action_detail_response(action_id: str, session: DbSession) -> OutputActionDetailResponse:
    try:
        action = get_output_action_or_raise(session, action_id)
    except OutputActionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    artifact = action.output_artifact
    return OutputActionDetailResponse(
        **build_output_action_summary_response(action).model_dump(),
        output_file_path=_output_file_path(artifact) if artifact is not None else None,
    )
