from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.services import indexing as indexing_service
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
        ],
    )


def test_list_jobs_returns_empty_list_initially(client: TestClient):
    response = client.get("/jobs")

    assert response.status_code == 200
    assert response.json() == []


def test_index_asset_creates_succeeded_job(client: TestClient, monkeypatch, sample_asset_file: Path):
    register_response = register_asset(client, sample_asset_file)
    asset_id = register_response.json()["id"]

    monkeypatch.setattr(
        indexing_service,
        "profile_asset_file",
        lambda _file_path: build_profile(sample_asset_file),
    )

    index_response = client.post(f"/assets/{asset_id}/index")
    assert index_response.status_code == 200

    jobs_response = client.get("/jobs")
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert len(jobs) == 1

    job = jobs[0]
    assert job["type"] == "index"
    assert job["status"] == "succeeded"
    assert job["target_asset_ids_json"] == [asset_id]
    assert job["config_json"] == {"execution": "inline", "trigger": "index_asset"}
    assert job["output_path"] is None
    assert job["error_message"] is None
    assert job["started_at"] is not None
    assert job["finished_at"] is not None

    detail_response = client.get(f"/jobs/{job['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json() == job


def test_index_asset_failure_creates_failed_job(client: TestClient, monkeypatch, sample_asset_file: Path):
    register_response = register_asset(client, sample_asset_file)
    asset_id = register_response.json()["id"]

    def raise_profile_error(_file_path: str):
        raise RuntimeError("bag inspection failed")

    monkeypatch.setattr(indexing_service, "profile_asset_file", raise_profile_error)

    index_response = client.post(f"/assets/{asset_id}/index")
    assert index_response.status_code == 422

    jobs_response = client.get("/jobs")
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert len(jobs) == 1
    assert jobs[0]["status"] == "failed"
    assert jobs[0]["error_message"] == "bag inspection failed"
    assert jobs[0]["target_asset_ids_json"] == [asset_id]


def test_get_job_returns_404_for_missing_job(client: TestClient):
    response = client.get("/jobs/not-a-real-job")

    assert response.status_code == 404
    assert response.json() == {"detail": "job not found: not-a-real-job"}


def test_list_jobs_orders_newest_first(client: TestClient, monkeypatch, tmp_path: Path):
    first_asset = tmp_path / "one.mcap"
    second_asset = tmp_path / "two.mcap"
    first_asset.write_bytes(b"one")
    second_asset.write_bytes(b"two")

    first_id = register_asset(client, first_asset).json()["id"]
    second_id = register_asset(client, second_asset).json()["id"]

    monkeypatch.setattr(
        indexing_service,
        "profile_asset_file",
        lambda file_path: build_profile(Path(file_path)),
    )

    assert client.post(f"/assets/{first_id}/index").status_code == 200
    assert client.post(f"/assets/{second_id}/index").status_code == 200

    jobs_response = client.get("/jobs")
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert [job["target_asset_ids_json"] for job in jobs] == [[second_id], [first_id]]


def test_reindex_all_creates_job_for_each_asset(client: TestClient, monkeypatch, tmp_path: Path):
    first_asset = tmp_path / "one.mcap"
    second_asset = tmp_path / "two.mcap"
    first_asset.write_bytes(b"one")
    second_asset.write_bytes(b"two")

    first_id = register_asset(client, first_asset).json()["id"]
    second_id = register_asset(client, second_asset).json()["id"]

    monkeypatch.setattr(
        indexing_service,
        "profile_asset_file",
        lambda file_path: build_profile(Path(file_path), topic_name="/points"),
    )

    response = client.post("/assets/reindex-all")
    assert response.status_code == 200

    jobs_response = client.get("/jobs")
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert len(jobs) == 2
    assert sorted(tuple(job["target_asset_ids_json"]) for job in jobs) == sorted(
        [(first_id,), (second_id,)]
    )
    assert all(job["config_json"] == {"execution": "inline", "trigger": "reindex_all"} for job in jobs)
    assert all(job["status"] == "succeeded" for job in jobs)
