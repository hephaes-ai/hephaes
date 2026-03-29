from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.config import get_settings
from app.workspace_bootstrap import resolve_backend_workspace
from hephaes import UnsupportedWorkspaceSchemaError
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
