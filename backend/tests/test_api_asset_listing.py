from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.services import indexing as indexing_service
from hephaes.models import BagMetadata, Topic


def register_asset(client: TestClient, asset_path: Path):
    return client.post("/assets/register", json={"file_path": str(asset_path)})


def build_profile(
    asset_path: Path,
    *,
    duration_seconds: float,
    start_time: datetime,
    topic_name: str = "/camera/front/image_raw",
) -> BagMetadata:
    resolved_path = asset_path.resolve()
    end_time = start_time + timedelta(seconds=duration_seconds)
    start_timestamp = int(start_time.timestamp() * 1e9)
    end_timestamp = int(end_time.timestamp() * 1e9)
    file_type = asset_path.suffix.lstrip(".").lower() or "unknown"
    storage_format = file_type if file_type in {"bag", "mcap"} else "unknown"

    return BagMetadata(
        compression_format="none",
        duration_seconds=duration_seconds,
        end_time_iso=end_time.isoformat().replace("+00:00", "Z"),
        end_timestamp=end_timestamp,
        file_path=str(resolved_path),
        file_size_bytes=asset_path.stat().st_size,
        message_count=max(1, int(duration_seconds * 10)),
        path=str(resolved_path),
        ros_version="ROS2",
        start_time_iso=start_time.isoformat().replace("+00:00", "Z"),
        start_timestamp=start_timestamp,
        storage_format=storage_format,
        topics=[
            Topic(
                message_count=max(1, int(duration_seconds * 5)),
                message_type="sensor_msgs/Image",
                name=topic_name,
                rate_hz=10.0,
            ),
            Topic(
                message_count=max(1, int(duration_seconds * 5)),
                message_type="sensor_msgs/Imu",
                name="/imu/data",
                rate_hz=20.0,
            ),
        ],
    )


def install_profile_map(monkeypatch, profiles_by_path: dict[str, BagMetadata]) -> None:
    def fake_profile(file_path: str) -> BagMetadata:
        return profiles_by_path[str(Path(file_path).resolve())]

    monkeypatch.setattr(indexing_service, "profile_asset_file", fake_profile)


def test_list_assets_returns_newest_registered_first(client: TestClient, tmp_path: Path):
    first_asset = tmp_path / "first.mcap"
    second_asset = tmp_path / "second.mcap"
    first_asset.write_bytes(b"first")
    second_asset.write_bytes(b"second")

    first_response = register_asset(client, first_asset)
    second_response = register_asset(client, second_asset)

    response = client.get("/assets")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [
        second_response.json()["id"],
        first_response.json()["id"],
    ]


def test_list_assets_filters_by_filename_case_insensitive(client: TestClient, tmp_path: Path):
    camera_asset = tmp_path / "CameraRun.MCAP"
    imu_asset = tmp_path / "imu_capture.mcap"
    camera_asset.write_bytes(b"camera")
    imu_asset.write_bytes(b"imu")

    camera_response = register_asset(client, camera_asset)
    register_asset(client, imu_asset)

    response = client.get("/assets", params={"search": "camera"})

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": camera_response.json()["id"],
            "file_path": str(camera_asset.resolve()),
            "file_name": camera_asset.name,
            "file_type": "mcap",
            "file_size": camera_asset.stat().st_size,
            "registered_time": camera_response.json()["registered_time"],
            "indexing_status": "pending",
            "last_indexed_time": None,
            "tags": [],
        }
    ]


def test_list_assets_filters_by_type_and_status(client: TestClient, monkeypatch, tmp_path: Path):
    indexed_asset = tmp_path / "indexed.mcap"
    pending_asset = tmp_path / "pending.bag"
    indexed_asset.write_bytes(b"indexed")
    pending_asset.write_bytes(b"pending")

    indexed_response = register_asset(client, indexed_asset)
    pending_response = register_asset(client, pending_asset)

    install_profile_map(
        monkeypatch,
        {
            str(indexed_asset.resolve()): build_profile(
                indexed_asset,
                duration_seconds=12.0,
                start_time=datetime(2026, 3, 16, 10, 0, 0, tzinfo=UTC),
            )
        },
    )

    index_response = client.post(f"/assets/{indexed_response.json()['id']}/index")
    assert index_response.status_code == 200

    type_response = client.get("/assets", params={"type": "bag"})
    assert type_response.status_code == 200
    assert [item["id"] for item in type_response.json()] == [pending_response.json()["id"]]

    status_response = client.get("/assets", params={"status": "indexed"})
    assert status_response.status_code == 200
    assert [item["id"] for item in status_response.json()] == [indexed_response.json()["id"]]

    combined_response = client.get("/assets", params={"type": "mcap", "status": "indexed"})
    assert combined_response.status_code == 200
    assert [item["id"] for item in combined_response.json()] == [indexed_response.json()["id"]]


def test_list_assets_filters_by_duration_and_start_time(client: TestClient, monkeypatch, tmp_path: Path):
    short_asset = tmp_path / "short.mcap"
    long_asset = tmp_path / "long.mcap"
    pending_asset = tmp_path / "pending.mcap"
    short_asset.write_bytes(b"short")
    long_asset.write_bytes(b"long")
    pending_asset.write_bytes(b"pending")

    short_response = register_asset(client, short_asset)
    long_response = register_asset(client, long_asset)
    pending_response = register_asset(client, pending_asset)

    install_profile_map(
        monkeypatch,
        {
            str(short_asset.resolve()): build_profile(
                short_asset,
                duration_seconds=5.0,
                start_time=datetime(2026, 3, 16, 10, 0, 0, tzinfo=UTC),
            ),
            str(long_asset.resolve()): build_profile(
                long_asset,
                duration_seconds=20.0,
                start_time=datetime(2026, 3, 16, 12, 0, 0, tzinfo=UTC),
            ),
        },
    )

    assert client.post(f"/assets/{short_response.json()['id']}/index").status_code == 200
    assert client.post(f"/assets/{long_response.json()['id']}/index").status_code == 200

    min_duration_response = client.get("/assets", params={"min_duration": "10"})
    assert min_duration_response.status_code == 200
    assert [item["id"] for item in min_duration_response.json()] == [long_response.json()["id"]]

    max_duration_response = client.get("/assets", params={"max_duration": "5"})
    assert max_duration_response.status_code == 200
    assert [item["id"] for item in max_duration_response.json()] == [short_response.json()["id"]]

    start_after_response = client.get("/assets", params={"start_after": "2026-03-16T11:00:00Z"})
    assert start_after_response.status_code == 200
    assert [item["id"] for item in start_after_response.json()] == [long_response.json()["id"]]

    start_before_response = client.get("/assets", params={"start_before": "2026-03-16T11:00:00Z"})
    assert start_before_response.status_code == 200
    assert [item["id"] for item in start_before_response.json()] == [short_response.json()["id"]]
    assert pending_response.json()["id"] not in [item["id"] for item in start_before_response.json()]


def test_list_assets_combines_multiple_query_params(client: TestClient, monkeypatch, tmp_path: Path):
    alpha_long_asset = tmp_path / "alpha_long.mcap"
    alpha_short_asset = tmp_path / "alpha_short.mcap"
    beta_asset = tmp_path / "beta.mcap"
    alpha_long_asset.write_bytes(b"alpha-long")
    alpha_short_asset.write_bytes(b"alpha-short")
    beta_asset.write_bytes(b"beta")

    alpha_long_response = register_asset(client, alpha_long_asset)
    alpha_short_response = register_asset(client, alpha_short_asset)
    register_asset(client, beta_asset)

    install_profile_map(
        monkeypatch,
        {
            str(alpha_long_asset.resolve()): build_profile(
                alpha_long_asset,
                duration_seconds=15.0,
                start_time=datetime(2026, 3, 16, 9, 0, 0, tzinfo=UTC),
            ),
            str(alpha_short_asset.resolve()): build_profile(
                alpha_short_asset,
                duration_seconds=3.0,
                start_time=datetime(2026, 3, 16, 9, 30, 0, tzinfo=UTC),
            ),
        },
    )

    assert client.post(f"/assets/{alpha_long_response.json()['id']}/index").status_code == 200
    assert client.post(f"/assets/{alpha_short_response.json()['id']}/index").status_code == 200

    response = client.get(
        "/assets",
        params={
            "search": "alpha",
            "type": "mcap",
            "status": "indexed",
            "min_duration": "10",
        },
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [alpha_long_response.json()["id"]]


def test_list_assets_ignores_empty_query_params(client: TestClient, sample_asset_file: Path):
    register_response = register_asset(client, sample_asset_file)

    response = client.get(
        "/assets",
        params={
            "search": "",
            "type": " ",
            "status": "",
            "min_duration": "",
            "max_duration": "",
            "start_after": "",
            "start_before": "",
        },
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": register_response.json()["id"],
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


def test_list_assets_returns_422_for_invalid_query_values(client: TestClient):
    invalid_duration_response = client.get("/assets", params={"min_duration": "not-a-number"})
    assert invalid_duration_response.status_code == 422
    assert "min_duration" in str(invalid_duration_response.json()["detail"])

    invalid_datetime_response = client.get("/assets", params={"start_after": "not-a-date"})
    assert invalid_datetime_response.status_code == 422
    assert "start_after" in str(invalid_datetime_response.json()["detail"])

    invalid_status_response = client.get("/assets", params={"status": "done"})
    assert invalid_status_response.status_code == 422
    assert "status" in str(invalid_status_response.json()["detail"])
