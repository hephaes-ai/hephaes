from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.services import indexing as indexing_service
from hephaes.models import BagMetadata, Topic


def register_asset(client: TestClient, asset_path: Path):
    return client.post("/assets/register", json={"file_path": str(asset_path)})


def build_profile(sample_asset_file: Path, *, topic_name: str = "/camera/front/image_raw") -> BagMetadata:
    resolved_path = sample_asset_file.resolve()
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
        file_size_bytes=sample_asset_file.stat().st_size,
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


def test_index_asset_success(client: TestClient, monkeypatch, sample_asset_file: Path):
    register_response = register_asset(client, sample_asset_file)
    asset_id = register_response.json()["id"]

    monkeypatch.setattr(
        indexing_service,
        "profile_asset_file",
        lambda _file_path: build_profile(sample_asset_file),
    )

    response = client.post(f"/assets/{asset_id}/index")

    assert response.status_code == 200
    body = response.json()
    assert body["asset"]["id"] == asset_id
    assert body["asset"]["indexing_status"] == "indexed"
    assert body["asset"]["last_indexed_time"] is not None
    assert body["metadata"] == {
        "default_episode": {
            "duration": 5.0,
            "episode_id": f"{asset_id}:default",
            "label": "Episode 1",
        },
        "duration": 5.0,
        "end_time": "2026-03-16T10:00:05Z",
        "indexing_error": None,
        "message_count": 12,
        "raw_metadata": {
            "compression_format": "none",
            "file_path": str(sample_asset_file.resolve()),
            "file_size_bytes": sample_asset_file.stat().st_size,
            "path": str(sample_asset_file.resolve()),
            "ros_version": "ROS2",
            "storage_format": "mcap",
        },
        "sensor_types": ["camera", "imu"],
        "start_time": "2026-03-16T10:00:00Z",
        "topic_count": 2,
        "topics": [
            {
                "message_count": 6,
                "message_type": "sensor_msgs/Image",
                "modality": "image",
                "name": "/camera/front/image_raw",
                "rate_hz": 10.0,
            },
            {
                "message_count": 6,
                "message_type": "sensor_msgs/Imu",
                "modality": "scalar_series",
                "name": "/imu/data",
                "rate_hz": 20.0,
            },
        ],
        "visualization_summary": {
            "default_lane_count": 2,
            "has_visualizable_streams": True,
        },
    }

    detail_response = client.get(f"/assets/{asset_id}")

    assert detail_response.status_code == 200
    assert detail_response.json()["metadata"] == body["metadata"]


def test_index_asset_failure_marks_asset_failed(client: TestClient, monkeypatch, sample_asset_file: Path):
    register_response = register_asset(client, sample_asset_file)
    asset_id = register_response.json()["id"]

    def raise_profile_error(_file_path: str):
        raise RuntimeError("bag inspection failed")

    monkeypatch.setattr(indexing_service, "profile_asset_file", raise_profile_error)

    response = client.post(f"/assets/{asset_id}/index")

    assert response.status_code == 422
    assert response.json() == {"detail": "bag inspection failed"}

    detail_response = client.get(f"/assets/{asset_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["asset"]["indexing_status"] == "failed"
    assert detail_response.json()["metadata"]["indexing_error"] == "bag inspection failed"


def test_reindex_all_pending_assets(client: TestClient, monkeypatch, tmp_path: Path):
    first_asset = tmp_path / "one.mcap"
    second_asset = tmp_path / "two.mcap"
    first_asset.write_bytes(b"one")
    second_asset.write_bytes(b"two")

    first_response = register_asset(client, first_asset)
    second_response = register_asset(client, second_asset)

    monkeypatch.setattr(
        indexing_service,
        "profile_asset_file",
        lambda file_path: build_profile(Path(file_path), topic_name="/points"),
    )

    response = client.post("/assets/reindex-all")

    assert response.status_code == 200
    body = response.json()
    assert body["total_requested"] == 2
    assert body["failed_assets"] == []
    assert sorted(asset["id"] for asset in body["indexed_assets"]) == sorted(
        [
            first_response.json()["id"],
            second_response.json()["id"],
        ]
    )
    assert all(asset["indexing_status"] == "indexed" for asset in body["indexed_assets"])
