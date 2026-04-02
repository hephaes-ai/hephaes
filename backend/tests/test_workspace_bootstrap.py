from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.config import get_settings
from app.workspace_bootstrap import bootstrap_workspace_registry, resolve_backend_workspace
from hephaes import UnsupportedWorkspaceSchemaError
from hephaes.workspace.errors import WorkspaceError
from hephaes.workspace import Workspace
from hephaes.workspace.schema import (
    WORKSPACE_DB_FILENAME,
    WORKSPACE_DIRNAME,
    WORKSPACE_SCHEMA_VERSION,
)


def _configure_backend_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    desktop_mode: bool,
) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setenv("HEPHAES_BACKEND_DATA_DIR", str(data_dir))
    monkeypatch.setenv("HEPHAES_BACKEND_DB_PATH", str(tmp_path / "backend.db"))
    monkeypatch.setenv("HEPHAES_BACKEND_OUTPUTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("HEPHAES_BACKEND_RAW_DATA_DIR", str(tmp_path / "raw"))
    monkeypatch.setenv("HEPHAES_BACKEND_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("HEPHAES_WORKSPACE_ROOT", str(tmp_path / "workspace"))
    if desktop_mode:
        monkeypatch.setenv("HEPHAES_DESKTOP_MODE", "1")
    else:
        monkeypatch.delenv("HEPHAES_DESKTOP_MODE", raising=False)
    get_settings.cache_clear()


def _write_unsupported_workspace(workspace_root: Path) -> Path:
    workspace_dir = workspace_root / WORKSPACE_DIRNAME
    workspace_dir.mkdir(parents=True, exist_ok=True)
    database_path = workspace_dir / WORKSPACE_DB_FILENAME
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            CREATE TABLE workspace_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO workspace_meta(key, value) VALUES ('schema_version', '9')"
        )
        connection.commit()
    finally:
        connection.close()
    return database_path


def test_resolve_backend_workspace_resets_unsupported_desktop_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_backend_env(monkeypatch, tmp_path, desktop_mode=True)
    settings = get_settings()
    _write_unsupported_workspace(settings.workspace_root)

    workspace = resolve_backend_workspace(settings)

    archived_workspaces = list((settings.data_dir / "workspace-archives").iterdir())
    assert len(archived_workspaces) == 1
    assert (archived_workspaces[0] / WORKSPACE_DB_FILENAME).is_file()
    assert workspace.root == settings.workspace_root

    reopened = Workspace.open(settings.workspace_root)
    assert reopened.database_path.is_file()
    connection = sqlite3.connect(reopened.database_path)
    try:
        row = connection.execute(
            "SELECT value FROM workspace_meta WHERE key = 'schema_version'"
        ).fetchone()
    finally:
        connection.close()
    assert row is not None
    assert int(row[0]) == WORKSPACE_SCHEMA_VERSION

    get_settings.cache_clear()


def test_resolve_backend_workspace_raises_for_unsupported_non_desktop_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_backend_env(monkeypatch, tmp_path, desktop_mode=False)
    settings = get_settings()
    _write_unsupported_workspace(settings.workspace_root)

    with pytest.raises(
        UnsupportedWorkspaceSchemaError,
        match="unsupported workspace schema version 9",
    ):
        resolve_backend_workspace(settings)

    assert not (settings.data_dir / "workspace-archives").exists()
    get_settings.cache_clear()


def test_resolve_backend_workspace_resets_for_legacy_generic_schema_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_backend_env(monkeypatch, tmp_path, desktop_mode=True)
    settings = get_settings()
    workspace_root = settings.workspace_root
    original_init = Workspace.init
    original_open = Workspace.open
    open_state = {"should_fail": True}

    monkeypatch.setattr(
        Workspace,
        "open",
        classmethod(
            lambda cls, root: (_ for _ in ()).throw(
                WorkspaceError("unsupported workspace schema version 9")
            )
            if open_state["should_fail"]
            else original_open(root)
        ),
    )

    def _init_workspace(cls, root, exist_ok=False):
        open_state["should_fail"] = False
        return original_init(root, exist_ok=exist_ok)

    monkeypatch.setattr(
        Workspace,
        "init",
        classmethod(_init_workspace),
    )
    _write_unsupported_workspace(workspace_root)

    workspace = resolve_backend_workspace(settings)

    assert workspace.root == workspace_root
    archived_workspaces = list((settings.data_dir / "workspace-archives").iterdir())
    assert len(archived_workspaces) == 1

    get_settings.cache_clear()


def test_resolve_backend_workspace_does_not_swallow_other_workspace_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_backend_env(monkeypatch, tmp_path, desktop_mode=True)
    settings = get_settings()
    Workspace.init(settings.workspace_root)

    monkeypatch.setattr(
        Workspace,
        "open",
        classmethod(
            lambda cls, root: (_ for _ in ()).throw(WorkspaceError("disk is unavailable"))
        ),
    )

    with pytest.raises(WorkspaceError, match="disk is unavailable"):
        resolve_backend_workspace(settings)

    assert not (settings.data_dir / "workspace-archives").exists()
    get_settings.cache_clear()


def test_resolve_backend_workspace_returns_none_when_registry_is_empty_and_no_legacy_workspace_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_backend_env(monkeypatch, tmp_path, desktop_mode=True)
    settings = get_settings()

    registry = bootstrap_workspace_registry(settings)
    workspace = resolve_backend_workspace(settings, registry)

    assert registry.list_workspaces() == []
    assert workspace is None

    get_settings.cache_clear()


def test_bootstrap_workspace_registry_imports_legacy_workspace_when_registry_is_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_backend_env(monkeypatch, tmp_path, desktop_mode=True)
    settings = get_settings()
    legacy_workspace = Workspace.init(settings.workspace_root)

    registry = bootstrap_workspace_registry(settings)
    registered_workspaces = registry.list_workspaces()

    assert len(registered_workspaces) == 1
    assert registered_workspaces[0].root_path == legacy_workspace.root
    assert registered_workspaces[0].status == "ready"
    assert registry.get_active_workspace_id() == registered_workspaces[0].id

    get_settings.cache_clear()


def test_resolve_backend_workspace_reconciles_to_last_used_registered_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_backend_env(monkeypatch, tmp_path, desktop_mode=True)
    settings = get_settings()
    first_workspace = Workspace.init(tmp_path / "first")
    second_workspace = Workspace.init(tmp_path / "second")

    registry = bootstrap_workspace_registry(settings)
    first = registry.register_workspace(first_workspace.root)
    second = registry.register_workspace(second_workspace.root)
    registry.set_active_workspace(first.id)
    registry.set_active_workspace(second.id)
    registry.set_active_workspace(None, update_last_opened=False)

    resolved = resolve_backend_workspace(settings, registry)

    assert resolved is not None
    assert resolved.root == second_workspace.root
    assert registry.get_active_workspace_id() == second.id

    get_settings.cache_clear()


def test_resolve_backend_workspace_falls_back_to_first_ready_workspace_when_none_were_used(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_backend_env(monkeypatch, tmp_path, desktop_mode=True)
    settings = get_settings()
    first_workspace = Workspace.init(tmp_path / "alpha")
    second_workspace = Workspace.init(tmp_path / "beta")

    registry = bootstrap_workspace_registry(settings)
    first = registry.register_workspace(first_workspace.root)
    registry.register_workspace(second_workspace.root)

    resolved = resolve_backend_workspace(settings, registry)

    assert resolved is not None
    assert resolved.root == first_workspace.root
    assert registry.get_active_workspace_id() == first.id

    get_settings.cache_clear()
