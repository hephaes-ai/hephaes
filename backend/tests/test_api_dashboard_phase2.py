from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.services import conversions as conversion_service
from app.services import dashboard as dashboard_service
from app.services import indexing as indexing_service
from hephaes.models import BagMetadata, Topic
import hephaes.workspace.assets as workspace_assets
import hephaes.workspace.configs.documents as workspace_config_documents
import hephaes.workspace.configs.mutations as workspace_config_mutations
import hephaes.workspace.conversions as workspace_conversions
import hephaes.workspace.drafts as workspace_drafts
import hephaes.workspace.jobs as workspace_jobs
import hephaes.workspace.outputs as workspace_outputs
import hephaes.workspace.tags as workspace_tags


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


def parse_api_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def count_entries_by_key(entries: list[dict[str, object]]) -> dict[str, int]:
    return {str(entry["key"]): int(entry["count"]) for entry in entries}


def patch_workspace_utc_now(monkeypatch, fixed_now: datetime) -> None:
    monkeypatch.setattr(workspace_assets, "_utc_now", lambda: fixed_now)
    monkeypatch.setattr(workspace_config_documents, "_utc_now", lambda: fixed_now)
    monkeypatch.setattr(workspace_config_mutations, "_utc_now", lambda: fixed_now)
    monkeypatch.setattr(workspace_conversions, "_utc_now", lambda: fixed_now)
    monkeypatch.setattr(workspace_drafts, "_utc_now", lambda: fixed_now)
    monkeypatch.setattr(workspace_jobs, "_utc_now", lambda: fixed_now)
    monkeypatch.setattr(workspace_outputs, "_utc_now", lambda: fixed_now)
    monkeypatch.setattr(workspace_tags, "_utc_now", lambda: fixed_now)


def _update_workspace_asset(
    client: TestClient,
    *,
    file_name: str,
    registered_at: datetime,
    last_indexed_at: datetime | None = None,
) -> None:
    with sqlite3.connect(client.app.state.workspace.database_path) as connection:
        connection.execute(
            """
            UPDATE assets
            SET registered_at = ?, last_indexed_at = ?
            WHERE file_name = ?
            """,
            (
                registered_at.isoformat(),
                last_indexed_at.isoformat() if last_indexed_at is not None else None,
                file_name,
            ),
        )
        connection.commit()


def _update_workspace_job(
    client: TestClient,
    *,
    kind: str,
    status: str,
    created_at: datetime,
    updated_at: datetime,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> None:
    with sqlite3.connect(client.app.state.workspace.database_path) as connection:
        connection.execute(
            """
            UPDATE jobs
            SET created_at = ?, updated_at = ?, started_at = ?, completed_at = ?
            WHERE kind = ? AND status = ?
            """,
            (
                created_at.isoformat(),
                updated_at.isoformat(),
                started_at.isoformat() if started_at is not None else None,
                completed_at.isoformat() if completed_at is not None else None,
                kind,
                status,
            ),
        )
        connection.commit()


def _update_workspace_conversion_run(
    client: TestClient,
    *,
    status: str,
    created_at: datetime,
    updated_at: datetime,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> None:
    with sqlite3.connect(client.app.state.workspace.database_path) as connection:
        connection.execute(
            """
            UPDATE conversion_runs
            SET created_at = ?, updated_at = ?, started_at = ?, completed_at = ?
            WHERE status = ?
            """,
            (
                created_at.isoformat(),
                updated_at.isoformat(),
                started_at.isoformat() if started_at is not None else None,
                completed_at.isoformat() if completed_at is not None else None,
                status,
            ),
        )
        connection.commit()


def _update_workspace_outputs(
    client: TestClient,
    *,
    created_at: datetime,
    updated_at: datetime,
) -> None:
    with sqlite3.connect(client.app.state.workspace.database_path) as connection:
        connection.execute(
            """
            UPDATE output_artifacts
            SET created_at = ?, updated_at = ?
            """,
            (
                created_at.isoformat(),
                updated_at.isoformat(),
            ),
        )
        connection.commit()


def test_dashboard_routes_return_zeroed_shapes_for_empty_catalog(
    client: TestClient,
    monkeypatch,
):
    fixed_now = datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(dashboard_service, "utc_now", lambda: fixed_now)
    patch_workspace_utc_now(monkeypatch, fixed_now)

    summary_response = client.get("/dashboard/summary")
    trends_response = client.get("/dashboard/trends?days=3")
    blockers_response = client.get("/dashboard/blockers")

    assert summary_response.status_code == 200
    assert trends_response.status_code == 200
    assert blockers_response.status_code == 200

    summary_body = summary_response.json()
    assert summary_body["inventory"] == {
        "asset_count": 0,
        "total_asset_bytes": 0,
        "registered_last_24h": 0,
        "registered_last_7d": 0,
        "registered_last_30d": 0,
    }
    assert summary_body["indexing"] == {
        "status_counts": {
            "pending": 0,
            "indexing": 0,
            "indexed": 0,
            "failed": 0,
        }
    }
    assert summary_body["jobs"] == {
        "active_count": 0,
        "failed_last_24h": 0,
        "status_counts": {
            "queued": 0,
            "running": 0,
            "succeeded": 0,
            "failed": 0,
        },
    }
    assert summary_body["conversions"] == {
        "status_counts": {
            "queued": 0,
            "running": 0,
            "succeeded": 0,
            "failed": 0,
        }
    }
    assert summary_body["outputs"] == {
        "output_count": 0,
        "total_output_bytes": 0,
        "outputs_created_last_7d": 0,
        "format_counts": [],
        "availability_counts": [
            {"key": "ready", "count": 0},
            {"key": "missing", "count": 0},
            {"key": "invalid", "count": 0},
        ],
    }
    assert summary_body["freshness"] == {
        "computed_at": summary_body["freshness"]["computed_at"],
        "latest_asset_registration_at": None,
        "latest_asset_indexed_at": None,
        "latest_job_update_at": None,
        "latest_conversion_update_at": None,
        "latest_output_update_at": None,
    }
    assert parse_api_datetime(summary_body["freshness"]["computed_at"]) == fixed_now

    assert blockers_response.json() == {
        "pending_assets": 0,
        "failed_assets": 0,
        "failed_jobs": 0,
        "failed_conversions": 0,
        "missing_outputs": 0,
        "invalid_outputs": 0,
    }

    trends_body = trends_response.json()
    assert trends_body["days"] == 3
    assert [bucket["date"] for bucket in trends_body["registrations_by_day"]] == [
        "2026-03-17",
        "2026-03-18",
        "2026-03-19",
    ]
    assert all(bucket["count"] == 0 for bucket in trends_body["registrations_by_day"])
    assert all(bucket["count"] == 0 for bucket in trends_body["job_failures_by_day"])
    assert all(bucket["count"] == 0 for bucket in trends_body["conversions_by_day"])
    assert all(bucket["count"] == 0 for bucket in trends_body["conversion_failures_by_day"])
    assert all(bucket["count"] == 0 for bucket in trends_body["outputs_created_by_day"])


def test_dashboard_routes_aggregate_mixed_operational_states(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
):
    fixed_now = datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(dashboard_service, "utc_now", lambda: fixed_now)
    patch_workspace_utc_now(monkeypatch, fixed_now)

    indexed_asset = tmp_path / "indexed.mcap"
    pending_asset = tmp_path / "pending.mcap"
    failed_asset = tmp_path / "failed.mcap"
    indexed_asset.write_bytes(b"indexed")
    pending_asset.write_bytes(b"pending")
    failed_asset.write_bytes(b"failed")

    indexed_asset_id = register_asset(client, indexed_asset).json()["id"]
    _pending_asset_id = register_asset(client, pending_asset).json()["id"]
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

    successful_output_dir = Path(successful_conversion.json()["output_path"])
    manifest_path = successful_output_dir / "episode_0001.manifest.json"
    manifest_size = manifest_path.stat().st_size
    (successful_output_dir / "episode_0001.parquet").unlink()

    _update_workspace_asset(
        client,
        file_name="indexed.mcap",
        registered_at=datetime(2026, 3, 19, 1, 0, 0, tzinfo=UTC),
        last_indexed_at=datetime(2026, 3, 18, 11, 5, 0, tzinfo=UTC),
    )
    _update_workspace_asset(
        client,
        file_name="pending.mcap",
        registered_at=datetime(2026, 3, 15, 14, 0, 0, tzinfo=UTC),
    )
    _update_workspace_asset(
        client,
        file_name="failed.mcap",
        registered_at=datetime(2026, 2, 10, 9, 0, 0, tzinfo=UTC),
    )
    _update_workspace_job(
        client,
        kind="index_asset",
        status="succeeded",
        created_at=datetime(2026, 3, 18, 11, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 3, 18, 11, 5, 0, tzinfo=UTC),
        started_at=datetime(2026, 3, 18, 11, 0, 30, tzinfo=UTC),
        completed_at=datetime(2026, 3, 18, 11, 5, 0, tzinfo=UTC),
    )
    _update_workspace_job(
        client,
        kind="index_asset",
        status="failed",
        created_at=datetime(2026, 3, 19, 8, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 3, 19, 8, 3, 0, tzinfo=UTC),
        started_at=datetime(2026, 3, 19, 8, 0, 30, tzinfo=UTC),
        completed_at=datetime(2026, 3, 19, 8, 3, 0, tzinfo=UTC),
    )
    _update_workspace_job(
        client,
        kind="conversion",
        status="succeeded",
        created_at=datetime(2026, 3, 18, 13, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 3, 18, 13, 2, 0, tzinfo=UTC),
        started_at=datetime(2026, 3, 18, 13, 0, 30, tzinfo=UTC),
        completed_at=datetime(2026, 3, 18, 13, 2, 0, tzinfo=UTC),
    )
    _update_workspace_job(
        client,
        kind="conversion",
        status="failed",
        created_at=datetime(2026, 3, 19, 7, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 3, 19, 7, 2, 0, tzinfo=UTC),
        started_at=datetime(2026, 3, 19, 7, 0, 30, tzinfo=UTC),
        completed_at=datetime(2026, 3, 19, 7, 2, 0, tzinfo=UTC),
    )
    _update_workspace_conversion_run(
        client,
        status="succeeded",
        created_at=datetime(2026, 3, 18, 13, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 3, 18, 13, 2, 0, tzinfo=UTC),
        started_at=datetime(2026, 3, 18, 13, 0, 30, tzinfo=UTC),
        completed_at=datetime(2026, 3, 18, 13, 2, 0, tzinfo=UTC),
    )
    _update_workspace_conversion_run(
        client,
        status="failed",
        created_at=datetime(2026, 3, 19, 7, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 3, 19, 7, 2, 0, tzinfo=UTC),
        started_at=datetime(2026, 3, 19, 7, 0, 30, tzinfo=UTC),
        completed_at=datetime(2026, 3, 19, 7, 2, 0, tzinfo=UTC),
    )
    _update_workspace_outputs(
        client,
        created_at=datetime(2026, 3, 18, 13, 3, 0, tzinfo=UTC),
        updated_at=datetime(2026, 3, 18, 13, 3, 0, tzinfo=UTC),
    )

    summary_response = client.get("/dashboard/summary")
    trends_response = client.get("/dashboard/trends")
    blockers_response = client.get("/dashboard/blockers")

    assert summary_response.status_code == 200
    assert trends_response.status_code == 200
    assert blockers_response.status_code == 200

    summary_body = summary_response.json()
    assert summary_body["inventory"] == {
        "asset_count": 3,
        "total_asset_bytes": len(b"indexed") + len(b"pending") + len(b"failed"),
        "registered_last_24h": 1,
        "registered_last_7d": 2,
        "registered_last_30d": 2,
    }
    assert summary_body["indexing"]["status_counts"] == {
        "pending": 1,
        "indexing": 0,
        "indexed": 1,
        "failed": 1,
    }
    # Jobs now come from workspace only (no backend DB visualization jobs)
    assert summary_body["jobs"] == {
        "active_count": 0,
        "failed_last_24h": 2,
        "status_counts": {
            "queued": 0,
            "running": 0,
            "succeeded": 2,
            "failed": 2,
        },
    }
    assert summary_body["conversions"]["status_counts"] == {
        "queued": 0,
        "running": 0,
        "succeeded": 1,
        "failed": 1,
    }
    assert summary_body["outputs"]["output_count"] == 2
    assert summary_body["outputs"]["total_output_bytes"] == manifest_size
    assert summary_body["outputs"]["outputs_created_last_7d"] == 2
    assert count_entries_by_key(summary_body["outputs"]["format_counts"]) == {
        "json": 1,
        "parquet": 1,
    }
    assert count_entries_by_key(summary_body["outputs"]["availability_counts"]) == {
        "ready": 1,
        "missing": 1,
        "invalid": 0,
    }

    freshness = summary_body["freshness"]
    assert parse_api_datetime(freshness["computed_at"]) == fixed_now
    assert parse_api_datetime(freshness["latest_asset_registration_at"]) == datetime(
        2026, 3, 19, 1, 0, 0, tzinfo=UTC
    )
    assert parse_api_datetime(freshness["latest_asset_indexed_at"]) == datetime(
        2026, 3, 18, 11, 5, 0, tzinfo=UTC
    )
    # latest_job_update_at from workspace jobs only: max of 2026-03-19T08:03 (index failed)
    assert parse_api_datetime(freshness["latest_job_update_at"]) == datetime(
        2026, 3, 19, 8, 3, 0, tzinfo=UTC
    )
    assert parse_api_datetime(freshness["latest_conversion_update_at"]) == datetime(
        2026, 3, 19, 7, 2, 0, tzinfo=UTC
    )
    assert parse_api_datetime(freshness["latest_output_update_at"]) == fixed_now

    trends_body = trends_response.json()
    assert trends_body["days"] == 7
    assert [bucket["date"] for bucket in trends_body["registrations_by_day"]] == [
        "2026-03-13",
        "2026-03-14",
        "2026-03-15",
        "2026-03-16",
        "2026-03-17",
        "2026-03-18",
        "2026-03-19",
    ]
    assert count_entries_by_key(
        [
            {"key": bucket["date"], "count": bucket["count"]}
            for bucket in trends_body["registrations_by_day"]
        ]
    ) == {
        "2026-03-13": 0,
        "2026-03-14": 0,
        "2026-03-15": 1,
        "2026-03-16": 0,
        "2026-03-17": 0,
        "2026-03-18": 0,
        "2026-03-19": 1,
    }
    assert count_entries_by_key(
        [
            {"key": bucket["date"], "count": bucket["count"]}
            for bucket in trends_body["job_failures_by_day"]
        ]
    )["2026-03-19"] == 2
    assert count_entries_by_key(
        [
            {"key": bucket["date"], "count": bucket["count"]}
            for bucket in trends_body["conversions_by_day"]
        ]
    ) == {
        "2026-03-13": 0,
        "2026-03-14": 0,
        "2026-03-15": 0,
        "2026-03-16": 0,
        "2026-03-17": 0,
        "2026-03-18": 1,
        "2026-03-19": 1,
    }
    assert count_entries_by_key(
        [
            {"key": bucket["date"], "count": bucket["count"]}
            for bucket in trends_body["conversion_failures_by_day"]
        ]
    )["2026-03-19"] == 1
    assert count_entries_by_key(
        [
            {"key": bucket["date"], "count": bucket["count"]}
            for bucket in trends_body["outputs_created_by_day"]
        ]
    )["2026-03-18"] == 2

    assert blockers_response.json() == {
        "pending_assets": 1,
        "failed_assets": 1,
        "failed_jobs": 2,
        "failed_conversions": 1,
        "missing_outputs": 1,
        "invalid_outputs": 0,
    }
