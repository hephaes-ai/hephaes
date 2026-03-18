from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.services import assets as asset_services


def register_asset(client: TestClient, asset_path: Path):
    return client.post("/assets/register", json={"file_path": str(asset_path)})


def register_asset_from_dialog(client: TestClient):
    return client.post("/assets/register-dialog")


def test_open_asset_file_dialog_uses_osascript_on_macos(monkeypatch):
    commands: list[tuple[list[str], str | None]] = []

    def fake_run(command, *, capture_output, check, input=None, text):
        commands.append((command, input))
        return SimpleNamespace(returncode=0, stdout="/tmp/one.mcap\n/tmp/two.bag\n", stderr="")

    monkeypatch.setattr(asset_services.sys, "platform", "darwin")
    monkeypatch.setattr(asset_services.shutil, "which", lambda name: "/usr/bin/osascript")
    monkeypatch.setattr(asset_services.subprocess, "run", fake_run)

    selected_paths = asset_services.open_asset_file_dialog()

    assert selected_paths == ["/tmp/one.mcap", "/tmp/two.bag"]
    assert commands == [
        (
            ["osascript", "-"],
            asset_services.MACOS_FILE_DIALOG_SCRIPT,
        )
    ]


def test_health_returns_ok(client: TestClient):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app_name": "Hephaes Backend",
    }


def test_register_asset_success(client: TestClient, sample_asset_file: Path):
    response = register_asset(client, sample_asset_file)

    assert response.status_code == 201
    assert response.json() == {
        "id": response.json()["id"],
        "file_path": str(sample_asset_file.resolve()),
        "file_name": sample_asset_file.name,
        "file_type": "mcap",
        "file_size": sample_asset_file.stat().st_size,
        "registered_time": response.json()["registered_time"],
        "indexing_status": "pending",
        "last_indexed_time": None,
    }


def test_register_asset_rejects_missing_file(client: TestClient, tmp_path: Path):
    missing_path = tmp_path / "missing_file.mcap"

    response = register_asset(client, missing_path)

    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]


def test_register_asset_rejects_duplicate_path(client: TestClient, sample_asset_file: Path):
    first = register_asset(client, sample_asset_file)
    second = register_asset(client, sample_asset_file)

    assert first.status_code == 201
    assert second.status_code == 409
    assert "already registered" in second.json()["detail"]


def test_register_asset_from_dialog_success(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    monkeypatch.setattr(
        asset_services,
        "open_asset_file_dialog",
        lambda: [str(sample_asset_file)],
    )

    response = register_asset_from_dialog(client)

    assert response.status_code == 200
    assert response.json() == {
        "canceled": False,
        "registered_assets": [
            {
                "id": response.json()["registered_assets"][0]["id"],
                "file_path": str(sample_asset_file.resolve()),
                "file_name": sample_asset_file.name,
                "file_type": "mcap",
                "file_size": sample_asset_file.stat().st_size,
                "registered_time": response.json()["registered_assets"][0]["registered_time"],
                "indexing_status": "pending",
                "last_indexed_time": None,
            }
        ],
        "skipped": [],
    }


def test_register_asset_from_dialog_canceled(client: TestClient, monkeypatch):
    monkeypatch.setattr(asset_services, "open_asset_file_dialog", lambda: [])

    response = register_asset_from_dialog(client)

    assert response.status_code == 200
    assert response.json() == {
        "canceled": True,
        "registered_assets": [],
        "skipped": [],
    }


def test_register_asset_from_dialog_skips_duplicates(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    register_asset(client, sample_asset_file)
    monkeypatch.setattr(
        asset_services,
        "open_asset_file_dialog",
        lambda: [str(sample_asset_file)],
    )

    response = register_asset_from_dialog(client)

    assert response.status_code == 200
    assert response.json() == {
        "canceled": False,
        "registered_assets": [],
        "skipped": [
            {
                "detail": f"asset already registered: {sample_asset_file.resolve()}",
                "file_path": str(sample_asset_file),
                "reason": "duplicate",
            }
        ],
    }


def test_register_asset_from_dialog_returns_503_when_unavailable(client: TestClient, monkeypatch):
    def raise_unavailable():
        raise asset_services.AssetDialogUnavailableError("native file picker is unavailable")

    monkeypatch.setattr(asset_services, "open_asset_file_dialog", raise_unavailable)

    response = register_asset_from_dialog(client)

    assert response.status_code == 503
    assert response.json() == {"detail": "native file picker is unavailable"}


def test_list_assets_returns_registered_asset(client: TestClient, sample_asset_file: Path):
    register_response = register_asset(client, sample_asset_file)
    asset_id = register_response.json()["id"]

    response = client.get("/assets")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": asset_id,
            "file_path": str(sample_asset_file.resolve()),
            "file_name": sample_asset_file.name,
            "file_type": "mcap",
            "file_size": sample_asset_file.stat().st_size,
            "registered_time": register_response.json()["registered_time"],
            "indexing_status": "pending",
            "last_indexed_time": None,
            "tags": [],
        }
    ]


def test_get_asset_detail_returns_registered_asset(client: TestClient, sample_asset_file: Path):
    register_response = register_asset(client, sample_asset_file)
    asset_id = register_response.json()["id"]

    response = client.get(f"/assets/{asset_id}")

    assert response.status_code == 200
    assert response.json() == {
        "asset": {
            "id": asset_id,
            "file_path": str(sample_asset_file.resolve()),
            "file_name": sample_asset_file.name,
            "file_type": "mcap",
            "file_size": sample_asset_file.stat().st_size,
            "registered_time": register_response.json()["registered_time"],
            "indexing_status": "pending",
            "last_indexed_time": None,
        },
        "metadata": None,
        "tags": [],
        "episodes": [],
        "related_jobs": [],
        "conversions": [],
    }


def test_get_asset_detail_returns_404_for_missing_asset(client: TestClient):
    response = client.get("/assets/not-a-real-id")

    assert response.status_code == 404
    assert response.json() == {"detail": "asset not found: not-a-real-id"}
