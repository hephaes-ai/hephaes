from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from hephaes.workspace.schema import WORKSPACE_DB_FILENAME


def _list_workspaces(client: TestClient) -> dict:
    response = client.get("/workspaces")
    assert response.status_code == 200
    return response.json()


def _create_workspace(
    client: TestClient,
    root_path: Path,
    *,
    name: str | None = None,
    activate: bool = True,
):
    payload: dict[str, object] = {"root_path": str(root_path), "activate": activate}
    if name is not None:
        payload["name"] = name
    return client.post("/workspaces", json=payload)


def _register_asset(client: TestClient, asset_path: Path, *, workspace_id: str | None = None):
    headers = None
    if workspace_id is not None:
        headers = {"X-Hephaes-Workspace-Id": workspace_id}
    return client.post("/assets/register", json={"file_path": str(asset_path)}, headers=headers)


def test_list_workspaces_returns_active_legacy_workspace(client: TestClient) -> None:
    payload = _list_workspaces(client)

    assert payload["active_workspace_id"] is not None
    assert len(payload["workspaces"]) == 1
    assert payload["workspaces"][0]["id"] == payload["active_workspace_id"]
    assert payload["workspaces"][0]["status"] == "ready"


def test_workspace_scoped_routes_require_workspace_when_registry_is_empty(
    empty_registry_client: TestClient,
) -> None:
    response = empty_registry_client.get("/assets")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "no ready workspace is available; create or open a workspace first"
    }


def test_create_workspace_initializes_workspace_and_activates_it(
    empty_registry_client: TestClient,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "created-workspace"

    response = _create_workspace(empty_registry_client, workspace_root, name="Demo Workspace")

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Demo Workspace"
    assert body["root_path"] == str(workspace_root.resolve())
    assert body["workspace_dir"] == str((workspace_root / ".hephaes").resolve())
    assert body["database_path"] == str((workspace_root / ".hephaes" / WORKSPACE_DB_FILENAME).resolve())
    assert body["status"] == "ready"
    assert (workspace_root / ".hephaes" / WORKSPACE_DB_FILENAME).is_file()

    listed = _list_workspaces(empty_registry_client)
    assert listed["active_workspace_id"] == body["id"]
    assert empty_registry_client.app.state.workspace is not None
    assert empty_registry_client.app.state.workspace.root == workspace_root.resolve()


def test_activate_workspace_changes_active_selection(
    client: TestClient,
    tmp_path: Path,
) -> None:
    initial = _list_workspaces(client)
    original_active_id = initial["active_workspace_id"]
    second_root = tmp_path / "second-workspace"
    create_response = _create_workspace(client, second_root, activate=False)
    assert create_response.status_code == 201
    created = create_response.json()

    activate_response = client.post(f"/workspaces/{created['id']}/activate")

    assert activate_response.status_code == 200
    assert activate_response.json()["id"] == created["id"]
    listed = _list_workspaces(client)
    assert listed["active_workspace_id"] == created["id"]
    assert listed["active_workspace_id"] != original_active_id
    assert client.app.state.workspace is not None
    assert client.app.state.workspace.root == second_root.resolve()


def test_list_workspaces_reconciles_active_selection_when_missing(
    client: TestClient,
    tmp_path: Path,
) -> None:
    registry = client.app.state.workspace_registry
    first = _list_workspaces(client)
    first_workspace_id = first["active_workspace_id"]
    second_root = tmp_path / "reconciled-workspace"
    created = _create_workspace(client, second_root, activate=False).json()

    registry.set_active_workspace(first_workspace_id)
    registry.set_active_workspace(created["id"])
    registry.set_active_workspace(None, update_last_opened=False)

    listed = _list_workspaces(client)

    assert listed["active_workspace_id"] == created["id"]


def test_workspace_header_override_uses_requested_workspace_without_changing_active_selection(
    client: TestClient,
    sample_asset_file: Path,
    tmp_path: Path,
) -> None:
    first = _list_workspaces(client)
    active_workspace_id = first["active_workspace_id"]
    second_root = tmp_path / "override-workspace"
    created = _create_workspace(client, second_root, activate=False).json()

    first_register = _register_asset(client, sample_asset_file)
    second_register = _register_asset(client, sample_asset_file, workspace_id=created["id"])
    assert first_register.status_code == 201
    assert second_register.status_code == 201

    default_assets = client.get("/assets")
    override_assets = client.get(
        "/assets",
        headers={"X-Hephaes-Workspace-Id": created["id"]},
    )

    assert default_assets.status_code == 200
    assert override_assets.status_code == 200
    assert len(default_assets.json()) == 1
    assert len(override_assets.json()) == 1
    assert _list_workspaces(client)["active_workspace_id"] == active_workspace_id


def test_delete_workspace_removes_workspace_directory_and_reconciles_active_selection(
    client: TestClient,
    tmp_path: Path,
) -> None:
    original_active_id = _list_workspaces(client)["active_workspace_id"]
    second_root = tmp_path / "delete-me"
    created = _create_workspace(client, second_root, activate=True).json()

    response = client.delete(f"/workspaces/{created['id']}")

    assert response.status_code == 204
    assert not (second_root / ".hephaes").exists()
    listed = _list_workspaces(client)
    assert all(workspace["id"] != created["id"] for workspace in listed["workspaces"])
    assert listed["active_workspace_id"] == original_active_id


def test_delete_workspace_blocks_when_workspace_has_active_jobs(
    client: TestClient,
    tmp_path: Path,
) -> None:
    second_root = tmp_path / "busy-workspace"
    created = _create_workspace(client, second_root, activate=True).json()
    client.app.state.workspace.create_job(kind="index")

    response = client.delete(f"/workspaces/{created['id']}")

    assert response.status_code == 409
    assert response.json()["detail"] == "cannot delete a workspace with queued or running jobs"
    assert (second_root / ".hephaes").is_dir()


def test_delete_workspace_rejects_mismatched_registered_directory(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
) -> None:
    second_root = tmp_path / "unsafe-delete"
    created = _create_workspace(client, second_root, activate=False).json()
    registry = client.app.state.workspace_registry
    original_get_workspace = registry.get_workspace

    def _tampered_get_workspace(workspace_id: str, *, refresh_status: bool = False):
        workspace = original_get_workspace(workspace_id, refresh_status=refresh_status)
        if workspace.id == created["id"]:
            return replace(workspace, workspace_dir=workspace.root_path)
        return workspace

    monkeypatch.setattr(registry, "get_workspace", _tampered_get_workspace)

    response = client.delete(f"/workspaces/{created['id']}")

    assert response.status_code == 409
    assert "refusing to delete" in response.json()["detail"]
    assert (second_root / ".hephaes").is_dir()


def test_request_header_returns_404_for_unknown_workspace(
    client: TestClient,
) -> None:
    response = client.get(
        "/assets",
        headers={"X-Hephaes-Workspace-Id": "ws_missing"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "workspace registry entry not found: ws_missing"
    }
