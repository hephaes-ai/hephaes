"""Workspace bootstrap helpers for backend startup."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from hephaes import (
    Workspace,
    WorkspaceError,
    WorkspaceNotFoundError,
)
from hephaes.workspace.schema import WORKSPACE_DIRNAME

from app.config import Settings
from app.services.workspaces import WorkspaceRegistry

logger = logging.getLogger(__name__)

try:
    from hephaes import UnsupportedWorkspaceSchemaError
except ImportError:
    UnsupportedWorkspaceSchemaError = None


def _is_unsupported_workspace_schema_error(exc: WorkspaceError) -> bool:
    if (
        UnsupportedWorkspaceSchemaError is not None
        and isinstance(exc, UnsupportedWorkspaceSchemaError)
    ):
        return True

    return "unsupported workspace schema version" in str(exc).lower()


def bootstrap_workspace_registry(settings: Settings) -> WorkspaceRegistry:
    registry = WorkspaceRegistry(settings.app_db_path)
    registry.initialize()

    existing_workspaces = registry.list_workspaces(refresh_status=True)
    if not existing_workspaces:
        _import_legacy_workspace_if_available(settings, registry)

    return registry


def resolve_backend_workspace(
    settings: Settings,
    registry: WorkspaceRegistry | None = None,
) -> Workspace | None:
    active_registry = registry or bootstrap_workspace_registry(settings)
    return active_registry.resolve_active_workspace()


def _import_legacy_workspace_if_available(
    settings: Settings,
    registry: WorkspaceRegistry,
) -> Workspace | None:
    legacy_workspace_dir = settings.workspace_root / WORKSPACE_DIRNAME
    if not legacy_workspace_dir.exists():
        return None

    workspace = _resolve_legacy_workspace(settings)
    registry.register_workspace(workspace.root, activate=True)
    return workspace


def _resolve_legacy_workspace(settings: Settings) -> Workspace:
    try:
        return Workspace.open(settings.workspace_root)
    except WorkspaceNotFoundError:
        return Workspace.init(settings.workspace_root, exist_ok=True)
    except WorkspaceError as exc:
        if not _is_unsupported_workspace_schema_error(exc):
            raise
        if not settings.desktop_mode:
            raise

        archived_workspace_dir = archive_workspace_dir(
            settings.workspace_root / WORKSPACE_DIRNAME,
            archive_root=settings.data_dir / "workspace-archives",
        )
        logger.warning(
            "reset incompatible desktop workspace at %s; archived previous "
            "workspace to %s; reason: %s",
            settings.workspace_root,
            archived_workspace_dir,
            exc,
        )
        return Workspace.init(settings.workspace_root, exist_ok=True)


def archive_workspace_dir(workspace_dir: Path, *, archive_root: Path) -> Path:
    if not workspace_dir.exists():
        raise FileNotFoundError(f"workspace directory does not exist: {workspace_dir}")

    archive_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_dir = archive_root / f"workspace-{timestamp}"
    suffix = 1
    while archive_dir.exists():
        archive_dir = archive_root / f"workspace-{timestamp}-{suffix}"
        suffix += 1

    shutil.move(str(workspace_dir), str(archive_dir))
    return archive_dir
