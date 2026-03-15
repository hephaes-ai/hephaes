from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def register_asset(client: TestClient, asset_path: Path):
    return client.post("/assets/register", json={"file_path": str(asset_path)})


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
        }
    }


def test_get_asset_detail_returns_404_for_missing_asset(client: TestClient):
    response = client.get("/assets/not-a-real-id")

    assert response.status_code == 404
    assert response.json() == {"detail": "asset not found: not-a-real-id"}
