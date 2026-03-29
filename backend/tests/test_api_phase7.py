from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.services import conversions as conversion_service
from app.services import indexing as indexing_service
from hephaes.models import BagMetadata, Topic


def register_asset(client: TestClient, asset_path: Path):
    return client.post("/assets/register", json={"file_path": str(asset_path)})


def upload_asset(client: TestClient, *, content: bytes, file_name: str):
    return client.post(
        "/assets/upload",
        content=content,
        headers={
            "content-type": "application/octet-stream",
            "x-file-name": file_name,
        },
    )


def build_profile(asset_path: Path, *, topic_name: str = "/camera/front/image_raw") -> BagMetadata:
    resolved_path = asset_path.resolve()
    start_time = datetime(2026, 3, 16, 10, 0, 0, tzinfo=UTC)
    end_time = datetime(2026, 3, 16, 10, 0, 5, tzinfo=UTC)
    start_timestamp = int(start_time.timestamp() * 1e9)
    end_timestamp = int(end_time.timestamp() * 1e9)

    return BagMetadata(
        compression_format="none",
        duration_seconds=5.0,
        end_time_iso=end_time.isoformat().replace("+00:00", "Z"),
        end_timestamp=end_timestamp,
        file_path=str(resolved_path),
        file_size_bytes=asset_path.stat().st_size,
        message_count=12,
        path=str(resolved_path),
        ros_version="ROS2",
        start_time_iso=start_time.isoformat().replace("+00:00", "Z"),
        start_timestamp=start_timestamp,
        storage_format="mcap",
        topics=[
            Topic(
                message_count=6,
                message_type="sensor_msgs/Image",
                name=topic_name,
                rate_hz=10.0,
            ),
            Topic(
                message_count=6,
                message_type="sensor_msgs/Imu",
                name="/imu/data",
                rate_hz=20.0,
            ),
        ],
    )


def test_upload_asset_success(client: TestClient, backend_raw_data_dir: Path):
    response = upload_asset(client, content=b"uploaded-data", file_name="uploaded_asset.mcap")

    assert response.status_code == 201
    body = response.json()
    stored_path = backend_raw_data_dir / "uploaded_asset.mcap"

    assert body == {
        "id": body["id"],
        "file_path": str(stored_path),
        "file_name": "uploaded_asset.mcap",
        "file_type": "mcap",
        "file_size": len(b"uploaded-data"),
        "registered_time": body["registered_time"],
        "indexing_status": "pending",
        "last_indexed_time": None,
    }
    assert stored_path.read_bytes() == b"uploaded-data"


def test_upload_asset_rejects_unsupported_type(client: TestClient):
    response = upload_asset(client, content=b"text-data", file_name="notes.txt")

    assert response.status_code == 400
    assert response.json() == {
        "detail": "unsupported asset type: notes.txt (supported: bag, mcap)"
    }


def test_upload_asset_rejects_empty_payload(client: TestClient):
    response = upload_asset(client, content=b"", file_name="empty.mcap")

    assert response.status_code == 400
    assert response.json() == {"detail": "uploaded file is empty"}


def test_upload_asset_rejects_duplicate_managed_file_name(client: TestClient):
    first_response = upload_asset(client, content=b"first", file_name="duplicate.mcap")
    second_response = upload_asset(client, content=b"second", file_name="duplicate.mcap")

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert "asset already registered" in second_response.json()["detail"]


def test_scan_directory_registers_supported_files_recursively(client: TestClient, tmp_path: Path):
    scan_root = tmp_path / "scan-root"
    nested_dir = scan_root / "nested"
    nested_dir.mkdir(parents=True)

    first_asset = scan_root / "one.mcap"
    second_asset = nested_dir / "two.bag"
    ignored_file = nested_dir / "ignore.txt"
    first_asset.write_bytes(b"one")
    second_asset.write_bytes(b"two")
    ignored_file.write_text("ignore")

    response = client.post(
        "/assets/scan-directory",
        json={"directory_path": str(scan_root), "recursive": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["scanned_directory"] == str(scan_root.resolve())
    assert body["recursive"] is True
    assert body["discovered_file_count"] == 2
    assert sorted(asset["file_name"] for asset in body["registered_assets"]) == ["one.mcap", "two.bag"]
    assert body["skipped"] == []


def test_scan_directory_skips_duplicates(client: TestClient, tmp_path: Path):
    scan_root = tmp_path / "scan-root"
    scan_root.mkdir()

    existing_asset = scan_root / "existing.mcap"
    fresh_asset = scan_root / "fresh.bag"
    existing_asset.write_bytes(b"existing")
    fresh_asset.write_bytes(b"fresh")

    register_asset(client, existing_asset)

    response = client.post(
        "/assets/scan-directory",
        json={"directory_path": str(scan_root), "recursive": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["discovered_file_count"] == 2
    assert [asset["file_name"] for asset in body["registered_assets"]] == ["fresh.bag"]
    assert body["skipped"] == [
        {
            "detail": f"asset already registered: {existing_asset.resolve()}",
            "file_path": str(existing_asset.resolve()),
            "reason": "duplicate",
        }
    ]


def test_scan_directory_rejects_invalid_directory(client: TestClient, tmp_path: Path):
    missing_directory = tmp_path / "missing-dir"

    response = client.post(
        "/assets/scan-directory",
        json={"directory_path": str(missing_directory), "recursive": True},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": f"asset directory does not exist: {missing_directory.resolve()}"
    }


def test_asset_detail_includes_jobs_and_conversions_for_uploaded_asset(
    client: TestClient,
    monkeypatch,
):
    upload_response = upload_asset(client, content=b"robot-data", file_name="mission.mcap")
    assert upload_response.status_code == 201
    asset = upload_response.json()
    asset_id = asset["id"]
    uploaded_path = Path(asset["file_path"])

    tag_response = client.post("/tags", json={"name": "field-run"})
    assert tag_response.status_code == 201
    tag_id = tag_response.json()["id"]

    attach_response = client.post(f"/assets/{asset_id}/tags", json={"tag_id": tag_id})
    assert attach_response.status_code == 200

    monkeypatch.setattr(
        indexing_service,
        "profile_asset_file",
        lambda _file_path: build_profile(uploaded_path),
    )

    index_response = client.post(f"/assets/{asset_id}/index")
    assert index_response.status_code == 200

    class FakeConverter:
        def __init__(self, **kwargs):
            self.output_dir = Path(kwargs["output_dir"])

        def convert(self) -> list[Path]:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            dataset_path = self.output_dir / "episode_0001.parquet"
            dataset_path.write_bytes(b"parquet-data")
            return [dataset_path]

    monkeypatch.setattr(conversion_service, "Converter", FakeConverter)

    conversion_response = client.post(
        "/conversions",
        json={"asset_ids": [asset_id], "output": {"format": "parquet"}},
    )
    assert conversion_response.status_code == 201

    detail_response = client.get(f"/assets/{asset_id}")

    assert detail_response.status_code == 200
    body = detail_response.json()
    assert body["asset"]["id"] == asset_id
    assert body["tags"] == [
        {
            "id": tag_id,
            "name": "field-run",
            "created_at": tag_response.json()["created_at"],
        }
    ]
    assert [job["type"] for job in body["related_jobs"]] == ["convert", "index"]
    assert all(asset_id in job["target_asset_ids_json"] for job in body["related_jobs"])
    assert len(body["conversions"]) == 1
    assert body["conversions"][0]["status"] == "succeeded"
    assert body["conversions"][0]["asset_ids"] == [asset_id]
