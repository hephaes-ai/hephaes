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
    get_latest_output_actions,
    get_output_action_or_raise,
    list_output_actions_for_output,
)
from hephaes import OutputArtifactNotFoundError, Workspace

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


def _workspace_output_job_id(workspace: Workspace, artifact) -> str | None:
    if artifact.conversion_run_id is None:
        return None
    run = workspace.get_conversion_run(artifact.conversion_run_id)
    if run is None:
        return None
    return run.job_id


def _workspace_output_asset_ids(workspace: Workspace, artifact) -> list[str]:
    if artifact.source_asset_id is not None:
        return [artifact.source_asset_id]
    if artifact.conversion_run_id is None:
        return []
    run = workspace.get_conversion_run(artifact.conversion_run_id)
    if run is None:
        return []
    return list(run.source_asset_ids)


def _normalize_output_metadata(metadata: dict) -> dict:
    normalized = dict(metadata)
    manifest = normalized.get("manifest")
    if not isinstance(manifest, dict):
        return normalized

    manifest_payload = dict(manifest)
    conversion_payload = manifest_payload.get("conversion")
    if (
        "payload_representation" not in manifest_payload
        and isinstance(conversion_payload, dict)
        and isinstance(conversion_payload.get("payload_representation"), dict)
    ):
        manifest_payload["payload_representation"] = dict(
            conversion_payload["payload_representation"]
        )
    normalized["manifest"] = manifest_payload
    return normalized


def _workspace_output_summary_response(
    workspace: Workspace,
    artifact,
    *,
    latest_action: OutputActionSummaryResponse | None = None,
) -> OutputArtifactSummaryResponse:
    detail = map_output_detail(
        artifact,
        job_id=_workspace_output_job_id(workspace, artifact),
        asset_ids=_workspace_output_asset_ids(workspace, artifact),
    )
    payload = detail.model_dump()
    payload.pop("file_path", None)
    payload["metadata"] = _normalize_output_metadata(payload.get("metadata", {}))
    payload["latest_action"] = latest_action.model_dump() if latest_action is not None else None
    return OutputArtifactSummaryResponse.model_validate(payload)


def _workspace_output_detail_response(
    workspace: Workspace,
    artifact,
    *,
    latest_action: OutputActionSummaryResponse | None = None,
) -> OutputArtifactDetailResponse:
    detail = map_output_detail(
        artifact,
        job_id=_workspace_output_job_id(workspace, artifact),
        asset_ids=_workspace_output_asset_ids(workspace, artifact),
    )
    payload = detail.model_dump()
    payload["metadata"] = _normalize_output_metadata(payload.get("metadata", {}))
    payload["latest_action"] = latest_action.model_dump() if latest_action is not None else None
    return OutputArtifactDetailResponse.model_validate(payload)


def _workspace_output_matches_filters(
    workspace: Workspace,
    artifact,
    query: OutputListQueryParams,
) -> bool:
    if query.conversion_id is not None and artifact.conversion_run_id != query.conversion_id:
        return False
    if query.asset_id is not None and query.asset_id not in _workspace_output_asset_ids(workspace, artifact):
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


def _refresh_workspace_artifact(workspace: Workspace, artifact):
    if artifact.conversion_run_id is None:
        return artifact
    run = workspace.get_conversion_run(artifact.conversion_run_id)
    if run is None:
        return artifact
    workspace.register_output_artifacts(
        output_root=run.output_dir,
        conversion_run_id=run.id,
        source_asset_id=artifact.source_asset_id,
        source_asset_path=artifact.source_asset_path,
        saved_config_id=artifact.saved_config_id,
    )
    return workspace.get_output_artifact_or_raise(artifact.id)


def _refresh_workspace_artifacts(workspace: Workspace, artifacts: list) -> list:
    refreshed_by_id: dict[str, object] = {}
    artifacts_by_run_id: dict[str | None, list] = {}
    for artifact in artifacts:
        artifacts_by_run_id.setdefault(artifact.conversion_run_id, []).append(artifact)

    for conversion_run_id, grouped_artifacts in artifacts_by_run_id.items():
        if conversion_run_id is None:
            for artifact in grouped_artifacts:
                refreshed_by_id[artifact.id] = artifact
            continue
        representative = grouped_artifacts[0]
        refreshed_representative = _refresh_workspace_artifact(workspace, representative)
        refreshed_by_id[refreshed_representative.id] = refreshed_representative
        for artifact in grouped_artifacts[1:]:
            refreshed_by_id[artifact.id] = workspace.get_output_artifact_or_raise(artifact.id)

    return [refreshed_by_id[artifact.id] for artifact in artifacts]


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


@router.get("", response_model=list[OutputArtifactSummaryResponse])
def list_outputs_route(
    workspace: WorkspaceDep,
    session: DbSession,
    query: Annotated[OutputListQueryParams, Depends(parse_list_outputs_query)],
) -> list[OutputArtifactSummaryResponse]:
    artifacts = _refresh_workspace_artifacts(workspace, [
        workspace.get_output_artifact_or_raise(summary.id)
        for summary in workspace.list_output_artifacts()
    ])
    filtered_artifacts = [
        artifact
        for artifact in artifacts
        if _workspace_output_matches_filters(workspace, artifact, query)
    ]
    latest_actions = {
        output_id: build_output_action_summary_response(action)
        for output_id, action in get_latest_output_actions(
            session,
            [artifact.id for artifact in filtered_artifacts],
        ).items()
    }
    responses = [
        _workspace_output_summary_response(
            workspace,
            artifact,
            latest_action=latest_actions.get(artifact.id),
        )
        for artifact in filtered_artifacts
    ]
    responses.sort(key=lambda artifact: (artifact.created_at, artifact.id), reverse=True)
    return responses[query.offset : query.offset + query.limit]


@router.get("/{output_id}", response_model=OutputArtifactDetailResponse)
def get_output_route(
    output_id: str,
    workspace: WorkspaceDep,
    session: DbSession,
) -> OutputArtifactDetailResponse:
    workspace_artifact = workspace.get_output_artifact(output_id)
    if workspace_artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"output artifact not found: {output_id}",
        )
    workspace_artifact = _refresh_workspace_artifact(workspace, workspace_artifact)
    latest_action = get_latest_output_actions(session, [output_id]).get(output_id)
    return _workspace_output_detail_response(
        workspace,
        workspace_artifact,
        latest_action=(
            build_output_action_summary_response(latest_action)
            if latest_action is not None
            else None
        ),
    )


@router.get("/{output_id}/content")
def get_output_content_route(
    output_id: str,
    workspace: WorkspaceDep,
) -> FileResponse:
    try:
        workspace_artifact = workspace.get_output_artifact(output_id)
        if workspace_artifact is None:
            raise OutputArtifactNotFoundError(f"output artifact not found: {output_id}")
        workspace_artifact = _refresh_workspace_artifact(workspace, workspace_artifact)
        artifact_path = Path(workspace_artifact.output_path)
        if not artifact_path.exists() or not artifact_path.is_file():
            raise OutputArtifactNotFoundError(
                f"output artifact content is unavailable: {output_id}"
            )
        media_type = workspace_artifact.media_type
        file_name = workspace_artifact.file_name
    except OutputArtifactNotFoundError as exc:
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
    workspace: WorkspaceDep,
    session: DbSession,
) -> OutputActionDetailResponse:
    service = OutputActionService(session, workspace)

    try:
        action = service.create_action(
            output_id=output_id,
            action_type=payload.action_type,
            config=payload.config,
        )
    except OutputActionValidationError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in detail.casefold()
            else HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc

    artifact = workspace.get_output_artifact_or_raise(action.output_artifact_id)
    return OutputActionDetailResponse(
        **build_output_action_summary_response(action).model_dump(),
        output_file_path=artifact.output_path,
    )


@router.get("/{output_id}/actions", response_model=list[OutputActionSummaryResponse])
def list_output_actions_route(
    output_id: str,
    workspace: WorkspaceDep,
    session: DbSession,
) -> list[OutputActionSummaryResponse]:
    try:
        workspace.get_output_artifact_or_raise(output_id)
        actions = list_output_actions_for_output(session, output_id)
    except OutputArtifactNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return [build_output_action_summary_response(action) for action in actions]


@router.get("/actions/{action_id}", response_model=OutputActionDetailResponse)
def get_output_action_route(
    action_id: str,
    workspace: WorkspaceDep,
    session: DbSession,
) -> OutputActionDetailResponse:
    return _build_output_action_detail_response(action_id, workspace, session)


@output_actions_router.get("/{action_id}", response_model=OutputActionDetailResponse)
def get_output_action_route_alias(
    action_id: str,
    workspace: WorkspaceDep,
    session: DbSession,
) -> OutputActionDetailResponse:
    return _build_output_action_detail_response(action_id, workspace, session)


def _build_output_action_detail_response(
    action_id: str,
    workspace: Workspace,
    session: DbSession,
) -> OutputActionDetailResponse:
    try:
        action = get_output_action_or_raise(session, action_id)
    except OutputActionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    artifact = workspace.get_output_artifact(action.output_artifact_id)
    return OutputActionDetailResponse(
        **build_output_action_summary_response(action).model_dump(),
        output_file_path=artifact.output_path if artifact is not None else None,
    )
