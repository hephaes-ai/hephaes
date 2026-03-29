"""Output artifact routes for conversion output catalog access."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import ValidationError
from pathlib import Path

from app.api._status import HTTP_422_UNPROCESSABLE_CONTENT
from app.dependencies import get_workspace
from app.mappers.workspace import map_output_detail
from app.schemas.outputs import (
    OutputArtifactDetailResponse,
    OutputArtifactSummaryResponse,
    OutputListQueryParams,
)
from hephaes import OutputArtifactNotFoundError, Workspace

router = APIRouter(prefix="/outputs", tags=["outputs"])
output_actions_router = APIRouter(prefix="/output-actions", tags=["outputs"])
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
) -> OutputArtifactSummaryResponse:
    detail = map_output_detail(
        artifact,
        job_id=_workspace_output_job_id(workspace, artifact),
        asset_ids=_workspace_output_asset_ids(workspace, artifact),
    )
    payload = detail.model_dump()
    payload.pop("file_path", None)
    payload["metadata"] = _normalize_output_metadata(payload.get("metadata", {}))
    return OutputArtifactSummaryResponse.model_validate(payload)


def _workspace_output_detail_response(
    workspace: Workspace,
    artifact,
) -> OutputArtifactDetailResponse:
    detail = map_output_detail(
        artifact,
        job_id=_workspace_output_job_id(workspace, artifact),
        asset_ids=_workspace_output_asset_ids(workspace, artifact),
    )
    payload = detail.model_dump()
    payload["metadata"] = _normalize_output_metadata(payload.get("metadata", {}))
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


@router.get("", response_model=list[OutputArtifactSummaryResponse])
def list_outputs_route(
    workspace: WorkspaceDep,
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
    responses = [
        _workspace_output_summary_response(workspace, artifact)
        for artifact in filtered_artifacts
    ]
    responses.sort(key=lambda artifact: (artifact.created_at, artifact.id), reverse=True)
    return responses[query.offset : query.offset + query.limit]


@router.get("/{output_id}", response_model=OutputArtifactDetailResponse)
def get_output_route(
    output_id: str,
    workspace: WorkspaceDep,
) -> OutputArtifactDetailResponse:
    workspace_artifact = workspace.get_output_artifact(output_id)
    if workspace_artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"output artifact not found: {output_id}",
        )
    workspace_artifact = _refresh_workspace_artifact(workspace, workspace_artifact)
    return _workspace_output_detail_response(workspace, workspace_artifact)


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
