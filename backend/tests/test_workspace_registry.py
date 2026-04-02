from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from app.services.workspaces import WorkspaceRegistry
from hephaes import Workspace


def test_workspace_registry_initializes_app_db_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "app.db"
    registry = WorkspaceRegistry(database_path)

    registry.initialize()

    assert database_path.is_file()
    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert "workspaces" in tables
    assert "app_state" in tables


def test_workspace_registry_registers_and_lists_workspaces(tmp_path: Path) -> None:
    database_path = tmp_path / "app.db"
    workspace_root = tmp_path / "demo"
    Workspace.init(workspace_root)
    registry = WorkspaceRegistry(database_path)
    registry.initialize()

    registered = registry.register_workspace(workspace_root, activate=True)
    listed = registry.list_workspaces()

    assert registry.get_active_workspace_id() == registered.id
    assert [workspace.id for workspace in listed] == [registered.id]
    assert listed[0].root_path == workspace_root
    assert listed[0].status == "ready"
    assert listed[0].last_opened_at is not None


def test_workspace_registry_reconciles_to_last_used_ready_workspace(tmp_path: Path) -> None:
    database_path = tmp_path / "app.db"
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    Workspace.init(first_root)
    Workspace.init(second_root)

    registry = WorkspaceRegistry(database_path)
    registry.initialize()
    first = registry.register_workspace(first_root)
    second = registry.register_workspace(second_root)

    registry.set_active_workspace(first.id)
    registry.set_active_workspace(second.id)
    registry.set_active_workspace(None, update_last_opened=False)

    reconciled = registry.reconcile_active_workspace()

    assert reconciled is not None
    assert reconciled.id == second.id
    assert registry.get_active_workspace_id() == second.id


def test_workspace_registry_falls_back_to_first_ready_workspace_when_none_were_used(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "app.db"
    first_root = tmp_path / "alpha"
    second_root = tmp_path / "beta"
    Workspace.init(first_root)
    Workspace.init(second_root)

    registry = WorkspaceRegistry(database_path)
    registry.initialize()
    first = registry.register_workspace(first_root)
    registry.register_workspace(second_root)

    reconciled = registry.reconcile_active_workspace()

    assert reconciled is not None
    assert reconciled.id == first.id
    assert registry.get_active_workspace_id() == first.id


def test_workspace_registry_skips_missing_active_workspace_during_reconciliation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "app.db"
    fallback_root = tmp_path / "fallback"
    missing_root = tmp_path / "missing"
    Workspace.init(fallback_root)
    Workspace.init(missing_root)

    registry = WorkspaceRegistry(database_path)
    registry.initialize()
    fallback = registry.register_workspace(fallback_root)
    missing = registry.register_workspace(missing_root, activate=True)

    shutil.rmtree(missing_root / ".hephaes")

    reconciled = registry.reconcile_active_workspace()

    assert reconciled is not None
    assert reconciled.id == fallback.id
    refreshed_missing = registry.get_workspace(missing.id)
    assert refreshed_missing.status == "missing"
