from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def register_asset(client: TestClient, asset_path: Path):
    return client.post("/assets/register", json={"file_path": str(asset_path)})


def create_tag(client: TestClient, name: str):
    return client.post("/tags", json={"name": name})


def attach_tag(client: TestClient, asset_id: str, tag_id: str):
    return client.post(f"/assets/{asset_id}/tags", json={"tag_id": tag_id})


def test_create_and_list_tags(client: TestClient):
    create_response = create_tag(client, "Night Run")
    second_response = create_tag(client, "Calibration")

    assert create_response.status_code == 201
    assert create_response.json() == {
        "id": create_response.json()["id"],
        "name": "Night Run",
        "created_at": create_response.json()["created_at"],
    }

    list_response = client.get("/tags")

    assert list_response.status_code == 200
    assert [item["name"] for item in list_response.json()] == ["Calibration", "Night Run"]
    assert [item["id"] for item in list_response.json()] == [
        second_response.json()["id"],
        create_response.json()["id"],
    ]


def test_create_tag_rejects_case_insensitive_duplicate(client: TestClient):
    first_response = create_tag(client, "Night Run")
    duplicate_response = create_tag(client, "night run")

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {"detail": "tag already exists: night run"}


def test_attach_tag_to_asset_and_include_in_detail(client: TestClient, sample_asset_file: Path):
    register_response = register_asset(client, sample_asset_file)
    asset_id = register_response.json()["id"]
    tag_response = create_tag(client, "Demo")
    tag_id = tag_response.json()["id"]

    attach_response = attach_tag(client, asset_id, tag_id)

    assert attach_response.status_code == 200
    assert attach_response.json()["tags"] == [
        {
            "id": tag_id,
            "name": "Demo",
            "created_at": tag_response.json()["created_at"],
        }
    ]

    detail_response = client.get(f"/assets/{asset_id}")

    assert detail_response.status_code == 200
    assert detail_response.json()["tags"] == attach_response.json()["tags"]


def test_attach_tag_rejects_duplicate_attachment(client: TestClient, sample_asset_file: Path):
    register_response = register_asset(client, sample_asset_file)
    tag_response = create_tag(client, "Demo")

    first_attach_response = attach_tag(client, register_response.json()["id"], tag_response.json()["id"])
    duplicate_attach_response = attach_tag(client, register_response.json()["id"], tag_response.json()["id"])

    assert first_attach_response.status_code == 200
    assert duplicate_attach_response.status_code == 409
    assert duplicate_attach_response.json() == {
        "detail": f"tag already attached to asset: Demo -> {sample_asset_file.name}"
    }


def test_remove_tag_from_asset(client: TestClient, sample_asset_file: Path):
    register_response = register_asset(client, sample_asset_file)
    asset_id = register_response.json()["id"]
    tag_response = create_tag(client, "Demo")
    tag_id = tag_response.json()["id"]
    assert attach_tag(client, asset_id, tag_id).status_code == 200

    remove_response = client.delete(f"/assets/{asset_id}/tags/{tag_id}")

    assert remove_response.status_code == 200
    assert remove_response.json()["tags"] == []

    detail_response = client.get(f"/assets/{asset_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["tags"] == []


def test_list_assets_filters_by_tag_and_composes_with_search(client: TestClient, tmp_path: Path):
    alpha_asset = tmp_path / "alpha.mcap"
    beta_asset = tmp_path / "beta.mcap"
    alpha_asset.write_bytes(b"alpha")
    beta_asset.write_bytes(b"beta")

    alpha_response = register_asset(client, alpha_asset)
    beta_response = register_asset(client, beta_asset)
    night_run_tag = create_tag(client, "Night Run")
    calibration_tag = create_tag(client, "Calibration")

    assert attach_tag(client, alpha_response.json()["id"], night_run_tag.json()["id"]).status_code == 200
    assert attach_tag(client, beta_response.json()["id"], calibration_tag.json()["id"]).status_code == 200

    tag_filter_response = client.get("/assets", params={"tag": "night run"})
    assert tag_filter_response.status_code == 200
    assert [item["id"] for item in tag_filter_response.json()] == [alpha_response.json()["id"]]

    combined_response = client.get("/assets", params={"tag": "night run", "search": "alpha"})
    assert combined_response.status_code == 200
    assert [item["id"] for item in combined_response.json()] == [alpha_response.json()["id"]]

    no_match_response = client.get("/assets", params={"tag": "night run", "search": "beta"})
    assert no_match_response.status_code == 200
    assert no_match_response.json() == []
