from __future__ import annotations

from pathlib import Path

import pytest

from hephaes import (
    AssetAlreadyRegisteredError,
    InvalidAssetPathError,
    Workspace,
    WorkspaceAlreadyExistsError,
    WorkspaceNotFoundError,
)


def test_workspace_init_creates_layout(tmp_path: Path) -> None:
    workspace = Workspace.init(tmp_path)

    assert workspace.root == tmp_path
    assert (tmp_path / ".hephaes").is_dir()
    assert (tmp_path / ".hephaes" / "workspace.sqlite3").is_file()
    assert (tmp_path / ".hephaes" / "outputs").is_dir()
    assert (tmp_path / ".hephaes" / "specs").is_dir()
    assert (tmp_path / ".hephaes" / "jobs").is_dir()


def test_workspace_init_rejects_duplicate_without_exist_ok(tmp_path: Path) -> None:
    Workspace.init(tmp_path)

    with pytest.raises(WorkspaceAlreadyExistsError):
        Workspace.init(tmp_path)


def test_workspace_open_resolves_parent_workspace(tmp_path: Path) -> None:
    Workspace.init(tmp_path)
    nested_dir = tmp_path / "nested" / "child"
    nested_dir.mkdir(parents=True)

    workspace = Workspace.open(nested_dir)

    assert workspace.root == tmp_path


def test_workspace_open_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceNotFoundError):
        Workspace.open(tmp_path)


def test_register_asset_persists_across_reopen(tmp_path: Path, tmp_mcap_file: Path) -> None:
    workspace = Workspace.init(tmp_path)

    registered = workspace.register_asset(tmp_mcap_file)
    reopened = Workspace.open(tmp_path)
    assets = reopened.list_assets()

    assert len(assets) == 1
    assert assets[0].id == registered.id
    assert assets[0].file_path == str(tmp_mcap_file.resolve())
    assert assets[0].file_type == "mcap"
    assert assets[0].indexing_status == "pending"


def test_register_asset_rejects_duplicates_by_default(tmp_path: Path, tmp_bag_file: Path) -> None:
    workspace = Workspace.init(tmp_path)
    workspace.register_asset(tmp_bag_file)

    with pytest.raises(AssetAlreadyRegisteredError):
        workspace.register_asset(tmp_bag_file)


def test_register_asset_supports_duplicate_skip(tmp_path: Path, tmp_bag_file: Path) -> None:
    workspace = Workspace.init(tmp_path)
    first = workspace.register_asset(tmp_bag_file)
    second = workspace.register_asset(tmp_bag_file, on_duplicate="skip")

    assert second.id == first.id
    assert len(workspace.list_assets()) == 1


def test_register_asset_supports_duplicate_refresh(tmp_path: Path, tmp_bag_file: Path) -> None:
    workspace = Workspace.init(tmp_path)
    first = workspace.register_asset(tmp_bag_file)
    tmp_bag_file.write_bytes(b"12345")

    refreshed = workspace.register_asset(tmp_bag_file, on_duplicate="refresh")

    assert refreshed.id == first.id
    assert refreshed.file_size == 5
    assert refreshed.updated_at >= first.updated_at


def test_register_asset_rejects_unsupported_types(tmp_path: Path) -> None:
    workspace = Workspace.init(tmp_path)
    unsupported = tmp_path / "notes.txt"
    unsupported.write_text("hello", encoding="utf-8")

    with pytest.raises(InvalidAssetPathError):
        workspace.register_asset(unsupported)
