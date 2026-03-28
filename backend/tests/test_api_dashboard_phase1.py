from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.services import conversions as conversion_service
from app.services import indexing as indexing_service
from app.services.jobs import JobService
from hephaes.models import BagMetadata, Topic


def register_asset(client: TestClient, asset_path: Path):
    return client.post("/assets/register", json={"file_path": str(asset_path)})


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


def install_dashboard_converter(monkeypatch) -> None:
    class FakeConverter:
        def __init__(self, **kwargs):
            self.output_dir = Path(kwargs["output_dir"])

        def convert(self) -> list[Path]:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            dataset_path = self.output_dir / "episode_0001.parquet"
            dataset_path.write_bytes(b"parquet-data")
            manifest_path = dataset_path.with_suffix(".manifest.json")
            manifest_path.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "episode_id": "episode_0001",
                        "dataset": {
                            "format": "parquet",
                            "rows_written": 12,
                            "field_names": ["camera_front_image_raw"],
                            "file_size_bytes": len(b"parquet-data"),
                        },
                        "source": {
                            "file_path": "/tmp/source.mcap",
                            "ros_version": "ROS2",
                            "storage_format": "mcap",
                        },
                        "temporal": {
                            "duration_seconds": 5.0,
                            "message_count": 12,
                            "start_time_iso": "2026-03-16T10:00:00Z",
                            "end_time_iso": "2026-03-16T10:00:05Z",
                        },
                    }
                ),
                encoding="utf-8",
            )
            return [dataset_path]

    monkeypatch.setattr(conversion_service, "Converter", FakeConverter)


def test_phase1_dashboard_routes_support_mixed_operational_states(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
):
    indexed_asset = tmp_path / "indexed.mcap"
    pending_asset = tmp_path / "pending.mcap"
    failed_asset = tmp_path / "failed.mcap"
    indexed_asset.write_bytes(b"indexed")
    pending_asset.write_bytes(b"pending")
    failed_asset.write_bytes(b"failed")

    indexed_asset_id = register_asset(client, indexed_asset).json()["id"]
    pending_asset_id = register_asset(client, pending_asset).json()["id"]
    failed_asset_id = register_asset(client, failed_asset).json()["id"]

    def fake_profile(file_path: str) -> BagMetadata:
        resolved_path = Path(file_path).resolve()
        if resolved_path == indexed_asset.resolve():
            return build_profile(indexed_asset)
        if resolved_path == failed_asset.resolve():
            raise RuntimeError("bag inspection failed")
        raise AssertionError(f"unexpected asset profile request: {resolved_path}")

    monkeypatch.setattr(indexing_service, "profile_asset_file", fake_profile)

    indexed_response = client.post(f"/assets/{indexed_asset_id}/index")
    failed_response = client.post(f"/assets/{failed_asset_id}/index")

    assert indexed_response.status_code == 200
    assert failed_response.status_code == 422

    session = client.app.state.session_factory()
    try:
        job_service = JobService(session)
        queued_job = job_service.create_job(
            job_type="prepare_visualization",
            target_asset_ids=[indexed_asset_id],
            config={"execution": "manual", "trigger": "dashboard_test"},
        )
        running_job = job_service.create_job(
            job_type="prepare_visualization",
            target_asset_ids=[pending_asset_id],
            config={"execution": "manual", "trigger": "dashboard_test"},
        )
        job_service.mark_job_running(running_job.id)
        assert queued_job.status == "queued"
    finally:
        session.close()

    install_dashboard_converter(monkeypatch)
    successful_conversion = client.post(
        "/conversions",
        json={"asset_ids": [indexed_asset_id], "output": {"format": "parquet"}},
    )
    assert successful_conversion.status_code == 201

    class FailingConverter:
        def __init__(self, **_kwargs):
            pass

        def convert(self) -> list[Path]:
            raise RuntimeError("conversion failed")

    monkeypatch.setattr(conversion_service, "Converter", FailingConverter)
    failed_conversion = client.post(
        "/conversions",
        json={"asset_ids": [indexed_asset_id], "output": {"format": "tfrecord", "compression": "gzip"}},
    )
    assert failed_conversion.status_code == 422

    successful_conversion_output_path = Path(successful_conversion.json()["output_path"])
    (successful_conversion_output_path / "episode_0001.parquet").unlink()

    assets_response = client.get("/assets")
    jobs_response = client.get("/jobs")
    conversions_response = client.get("/conversions")
    outputs_response = client.get("/outputs")

    assert assets_response.status_code == 200
    assert jobs_response.status_code == 200
    assert conversions_response.status_code == 200
    assert outputs_response.status_code == 200

    asset_statuses = [asset["indexing_status"] for asset in assets_response.json()]
    assert asset_statuses.count("indexed") == 1
    assert asset_statuses.count("pending") == 1
    assert asset_statuses.count("failed") == 1

    job_statuses = [job["status"] for job in jobs_response.json()]
    assert "succeeded" in job_statuses
    assert "failed" in job_statuses
    assert "queued" not in job_statuses
    assert "running" not in job_statuses

    conversion_statuses = [conversion["status"] for conversion in conversions_response.json()]
    assert conversion_statuses.count("succeeded") == 1
    assert conversion_statuses.count("failed") == 1

    outputs = outputs_response.json()
    assert len(outputs) == 2
    output_formats = [output["format"] for output in outputs]
    output_availability = [output["availability_status"] for output in outputs]
    assert output_formats.count("parquet") == 1
    assert output_formats.count("json") == 1
    assert output_availability.count("missing") == 1
    assert output_availability.count("ready") == 1
