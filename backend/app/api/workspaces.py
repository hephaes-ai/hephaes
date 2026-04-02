"""Workspace registry routes for multi-workspace desktop support."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.dependencies import get_workspace_registry, sync_active_workspace_state
from app.schemas.workspaces import (
    WorkspaceCreateRequest,
    WorkspaceRegistryListResponse,
    WorkspaceRegistrySummaryResponse,
)
from app.services.workspaces import (
    RegisteredWorkspace,
    WorkspaceRegistry,
    WorkspaceRegistryError,
    WorkspaceRegistryNotFoundError,
)
from hephaes import Workspace, WorkspaceError
from hephaes.workspace.schema import WORKSPACE_DIRNAME

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
WorkspaceRegistryDep = Annotated[WorkspaceRegistry, Depends(get_workspace_registry)]


def _to_workspace_summary_response(
    workspace: RegisteredWorkspace,
) -> WorkspaceRegistrySummaryResponse:
    active_job_count = 0

    if workspace.status == "ready":
        try:
            resolved_workspace = Workspace.open(workspace.root_path)
        except WorkspaceError:
            active_job_count = 0
        else:
            active_job_count = sum(
                1
                for job in resolved_workspace.list_jobs()
                if job.status in {"pending", "running"}
            )

    return WorkspaceRegistrySummaryResponse.model_validate(
        {
            "active_job_count": active_job_count,
            "id": workspace.id,
            "name": workspace.name,
            "root_path": str(workspace.root_path),
            "workspace_dir": str(workspace.workspace_dir),
            "database_path": str(workspace.database_path),
            "created_at": workspace.created_at,
            "updated_at": workspace.updated_at,
            "last_opened_at": workspace.last_opened_at,
            "status": workspace.status,
            "status_reason": workspace.status_reason,
        }
    )


def _build_workspace_list_response(
    registry: WorkspaceRegistry,
) -> WorkspaceRegistryListResponse:
    active_workspace = registry.reconcile_active_workspace()
    workspaces = registry.list_workspaces(refresh_status=False)
    return WorkspaceRegistryListResponse(
        active_workspace_id=active_workspace.id if active_workspace is not None else None,
        workspaces=[_to_workspace_summary_response(workspace) for workspace in workspaces],
    )


def _normalize_root_path(root_path: str) -> Path:
    return Path(root_path).expanduser().resolve(strict=False)


def _ensure_workspace_exists(root_path: Path) -> Workspace:
    workspace_dir = root_path / WORKSPACE_DIRNAME
    try:
        if workspace_dir.exists():
            return Workspace.open(root_path)
        return Workspace.init(root_path, exist_ok=True)
    except WorkspaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


def _validate_delete_target(workspace: RegisteredWorkspace) -> Path:
    normalized_root = workspace.root_path.expanduser().resolve(strict=False)
    expected_workspace_dir = (normalized_root / WORKSPACE_DIRNAME).resolve(strict=False)
    registered_workspace_dir = workspace.workspace_dir.expanduser().resolve(strict=False)

    if registered_workspace_dir != expected_workspace_dir:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="refusing to delete a workspace whose registered directory does not match the expected .hephaes location",
        )
    if registered_workspace_dir == normalized_root:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="refusing to delete the workspace root directly",
        )
    return expected_workspace_dir


def _ensure_workspace_has_no_active_jobs(workspace: RegisteredWorkspace) -> None:
    if workspace.status != "ready":
        return

    try:
        resolved_workspace = Workspace.open(workspace.root_path)
    except WorkspaceError:
        return

    active_jobs = [
        job.id for job in resolved_workspace.list_jobs() if job.status in {"pending", "running"}
    ]
    if active_jobs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cannot delete a workspace with queued or running jobs",
        )


@router.get("", response_model=WorkspaceRegistryListResponse)
def list_workspaces_route(
    request: Request,
    registry: WorkspaceRegistryDep,
) -> WorkspaceRegistryListResponse:
    response = _build_workspace_list_response(registry)
    request.app.state.workspace = registry.resolve_active_workspace()
    return response


@router.post(
    "",
    response_model=WorkspaceRegistrySummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace_route(
    payload: WorkspaceCreateRequest,
    request: Request,
    registry: WorkspaceRegistryDep,
) -> WorkspaceRegistrySummaryResponse:
    root_path = _normalize_root_path(payload.root_path)
    _ensure_workspace_exists(root_path)

    try:
        registered_workspace = registry.register_workspace(
            root_path,
            name=payload.name,
            activate=payload.activate,
        )
    except WorkspaceRegistryError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if payload.activate:
        request.app.state.workspace = registry.resolve_active_workspace()
    return _to_workspace_summary_response(registered_workspace)


@router.post("/{workspace_id}/activate", response_model=WorkspaceRegistrySummaryResponse)
def activate_workspace_route(
    workspace_id: str,
    request: Request,
    registry: WorkspaceRegistryDep,
) -> WorkspaceRegistrySummaryResponse:
    try:
        registry.resolve_workspace_by_id(workspace_id)
        activated_workspace = registry.set_active_workspace(workspace_id)
    except WorkspaceRegistryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except WorkspaceRegistryError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    request.app.state.workspace = sync_active_workspace_state(request)
    assert activated_workspace is not None
    return _to_workspace_summary_response(activated_workspace)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace_route(
    workspace_id: str,
    request: Request,
    registry: WorkspaceRegistryDep,
) -> Response:
    try:
        registered_workspace = registry.get_workspace(workspace_id, refresh_status=True)
    except WorkspaceRegistryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    delete_target = _validate_delete_target(registered_workspace)
    _ensure_workspace_has_no_active_jobs(registered_workspace)

    if delete_target.exists():
        if not delete_target.is_dir():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"workspace path is not a directory: {delete_target}",
            )
        shutil.rmtree(delete_target)

    registry.remove_workspace(workspace_id)
    request.app.state.workspace = registry.resolve_active_workspace()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
