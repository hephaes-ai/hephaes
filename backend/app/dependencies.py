"""Shared FastAPI dependencies for backend adapters."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException, Request, status
from hephaes import Workspace

from app.services.workspaces import WorkspaceRegistry, WorkspaceRegistryError, WorkspaceRegistryNotFoundError

WORKSPACE_HEADER_NAME = "X-Hephaes-Workspace-Id"


def get_workspace_registry(request: Request) -> WorkspaceRegistry:
    workspace_registry = getattr(request.app.state, "workspace_registry", None)
    if workspace_registry is None:  # pragma: no cover - defensive startup guard
        raise RuntimeError("workspace registry is not initialized on app state")
    if not isinstance(workspace_registry, WorkspaceRegistry):
        raise RuntimeError("workspace registry is misconfigured on app state")
    return workspace_registry


def sync_active_workspace_state(request: Request) -> Workspace | None:
    workspace = get_workspace_registry(request).resolve_active_workspace()
    request.app.state.workspace = workspace
    return workspace


def get_workspace(
    request: Request,
    workspace_id: Annotated[str | None, Header(alias=WORKSPACE_HEADER_NAME)] = None,
) -> Workspace:
    workspace_registry = get_workspace_registry(request)

    if workspace_id is not None and workspace_id.strip():
        try:
            return workspace_registry.resolve_workspace_by_id(workspace_id.strip())
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

    workspace = sync_active_workspace_state(request)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="no ready workspace is available; create or open a workspace first",
        )
    return workspace
