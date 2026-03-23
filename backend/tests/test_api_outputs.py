from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.models import OutputArtifact
from app.services import conversions as conversion_service
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


def index_registered_asset(client: TestClient, monkeypatch, asset_path: Path) -> str:
    register_response = register_asset(client, asset_path)
    asset_id = register_response.json()["id"]

    monkeypatch.setattr(
        indexing_service,
        "profile_asset_file",
        lambda _file_path: build_profile(asset_path),
    )

    index_response = client.post(f"/assets/{asset_id}/index")
    assert index_response.status_code == 200
    return asset_id


def install_fake_converter(monkeypatch, *, with_report: bool = False) -> None:
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
                        "conversion": {
                            "payload_representation": {
                                "image_payload_contract": "bytes_v2",
                                "payload_encoding": "typed_features",
                                "null_encoding": "presence_flag",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            if with_report:
                report_path = dataset_path.with_name(f"{dataset_path.stem}.report.md")
                report_path.write_text("# conversion report\n", encoding="utf-8")
            return [dataset_path]

    monkeypatch.setattr(conversion_service, "Converter", FakeConverter)


def create_conversion(client: TestClient, monkeypatch, sample_asset_file: Path) -> tuple[str, dict]:
    asset_id = index_registered_asset(client, monkeypatch, sample_asset_file)
    install_fake_converter(monkeypatch)

    response = client.post(
        "/conversions",
        json={"asset_ids": [asset_id], "output": {"format": "parquet"}},
    )
    assert response.status_code == 201
    return asset_id, response.json()


def test_list_outputs_returns_empty_list_initially(client: TestClient):
    response = client.get("/outputs")

    assert response.status_code == 200
    assert response.json() == []


def test_list_outputs_orders_newest_conversion_first(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
):
    first_asset = tmp_path / "first.mcap"
    second_asset = tmp_path / "second.mcap"
    first_asset.write_bytes(b"first")
    second_asset.write_bytes(b"second")

    first_asset_id = index_registered_asset(client, monkeypatch, first_asset)
    second_asset_id = index_registered_asset(client, monkeypatch, second_asset)
    install_fake_converter(monkeypatch)

    first_conversion = client.post(
        "/conversions",
        json={"asset_ids": [first_asset_id], "output": {"format": "parquet"}},
    )
    second_conversion = client.post(
        "/conversions",
        json={"asset_ids": [second_asset_id], "output": {"format": "parquet"}},
    )

    assert first_conversion.status_code == 201
    assert second_conversion.status_code == 201

    response = client.get("/outputs")
    assert response.status_code == 200

    outputs = response.json()
    assert len(outputs) == 4
    assert [item["conversion_id"] for item in outputs[:2]] == [second_conversion.json()["id"]] * 2
    assert [item["conversion_id"] for item in outputs[2:]] == [first_conversion.json()["id"]] * 2


def test_outputs_are_registered_and_filterable_after_conversion(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id, conversion = create_conversion(client, monkeypatch, sample_asset_file)

    response = client.get("/outputs")
    assert response.status_code == 200

    outputs = response.json()
    assert len(outputs) == 2

    outputs_by_name = {item["file_name"]: item for item in outputs}
    dataset = outputs_by_name["episode_0001.parquet"]
    manifest = outputs_by_name["episode_0001.manifest.json"]

    assert dataset["conversion_id"] == conversion["id"]
    assert dataset["job_id"] == conversion["job_id"]
    assert dataset["asset_ids"] == [asset_id]
    assert dataset["format"] == "parquet"
    assert dataset["role"] == "dataset"
    assert dataset["availability_status"] == "ready"
    assert dataset["size_bytes"] == len(b"parquet-data")
    assert dataset["content_url"] == f"/outputs/{dataset['id']}/content"
    assert dataset["metadata"]["manifest"]["episode_id"] == "episode_0001"
    assert dataset["metadata"]["manifest"]["payload_representation"] == {
        "image_payload_contract": "bytes_v2",
        "payload_encoding": "typed_features",
        "null_encoding": "presence_flag",
    }

    assert manifest["format"] == "json"
    assert manifest["role"] == "manifest"
    assert manifest["availability_status"] == "ready"
    assert manifest["metadata"]["manifest"]["dataset"]["rows_written"] == 12

    filtered_response = client.get(
        "/outputs",
        params={"asset_id": asset_id, "format": "parquet", "role": "dataset"},
    )
    assert filtered_response.status_code == 200
    assert [item["id"] for item in filtered_response.json()] == [dataset["id"]]

    conversion_filtered_response = client.get("/outputs", params={"conversion_id": conversion["id"]})
    assert conversion_filtered_response.status_code == 200
    assert {item["id"] for item in conversion_filtered_response.json()} == {dataset["id"], manifest["id"]}


def test_outputs_register_report_sidecars_when_present(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_registered_asset(client, monkeypatch, sample_asset_file)
    install_fake_converter(monkeypatch, with_report=True)

    response = client.post(
        "/conversions",
        json={"asset_ids": [asset_id], "output": {"format": "parquet"}},
    )
    assert response.status_code == 201

    outputs = client.get("/outputs").json()
    assert {item["role"] for item in outputs} == {"dataset", "manifest", "report"}
    report = next(item for item in outputs if item["role"] == "report")
    assert report["format"] == "md"
    assert report["file_name"] == "episode_0001.report.md"


def test_get_output_detail_and_content(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    _asset_id, conversion = create_conversion(client, monkeypatch, sample_asset_file)
    outputs = client.get("/outputs", params={"format": "parquet"}).json()
    output_id = outputs[0]["id"]

    detail_response = client.get(f"/outputs/{output_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == output_id
    assert detail["file_path"] == str(Path(conversion["output_path"]) / "episode_0001.parquet")

    content_response = client.get(detail["content_url"])
    assert content_response.status_code == 200
    assert content_response.content == b"parquet-data"


def test_outputs_refresh_missing_file_status_and_content_returns_404(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    _asset_id, conversion = create_conversion(client, monkeypatch, sample_asset_file)
    dataset_path = Path(conversion["output_path"]) / "episode_0001.parquet"
    dataset_output = client.get("/outputs", params={"format": "parquet"}).json()[0]

    dataset_path.unlink()

    missing_response = client.get("/outputs", params={"availability": "missing"})
    assert missing_response.status_code == 200
    missing_outputs = missing_response.json()
    assert [item["id"] for item in missing_outputs] == [dataset_output["id"]]

    content_response = client.get(f"/outputs/{dataset_output['id']}/content")
    assert content_response.status_code == 404
    assert content_response.json() == {
        "detail": f"output artifact content is unavailable: {dataset_output['id']}"
    }


def test_outputs_lazy_backfill_recreates_deleted_artifact_rows(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    _asset_id, _conversion = create_conversion(client, monkeypatch, sample_asset_file)
    original_outputs = client.get("/outputs").json()
    assert len(original_outputs) == 2

    session = client.app.state.session_factory()
    try:
        session.execute(delete(OutputArtifact))
        session.commit()
    finally:
        session.close()

    restored_response = client.get("/outputs")
    assert restored_response.status_code == 200
    restored_outputs = restored_response.json()
    assert len(restored_outputs) == 2
    assert {item["file_name"] for item in restored_outputs} == {
        "episode_0001.parquet",
        "episode_0001.manifest.json",
    }


def test_output_actions_refresh_metadata_updates_latest_action_and_detail(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    _asset_id, conversion = create_conversion(client, monkeypatch, sample_asset_file)
    dataset_output = client.get("/outputs", params={"format": "parquet"}).json()[0]

    dataset_path = Path(conversion["output_path"]) / "episode_0001.parquet"
    dataset_path.write_bytes(b"parquet-data-updated")

    create_action_response = client.post(
        f"/outputs/{dataset_output['id']}/actions",
        json={"action_type": "refresh_metadata", "config": {"reason": "test"}},
    )
    assert create_action_response.status_code == 201
    action = create_action_response.json()
    assert action["output_id"] == dataset_output["id"]
    assert action["action_type"] == "refresh_metadata"
    assert action["status"] == "succeeded"
    assert action["config"] == {"reason": "test"}
    assert action["result"]["availability_status"] == "ready"
    assert action["result"]["size_bytes"] == len(b"parquet-data-updated")
    assert action["output_path"] == str(Path(conversion["output_path"]).parents[1] / "actions" / action["id"])
    assert action["output_file_path"] == str(dataset_path)

    result_file = Path(action["output_path"]) / "result.json"
    assert result_file.exists()

    list_actions_response = client.get(f"/outputs/{dataset_output['id']}/actions")
    assert list_actions_response.status_code == 200
    listed_actions = list_actions_response.json()
    assert [item["id"] for item in listed_actions] == [action["id"]]
    assert listed_actions[0]["status"] == "succeeded"

    action_detail_response = client.get(f"/outputs/actions/{action['id']}")
    assert action_detail_response.status_code == 200
    assert action_detail_response.json() == action

    output_detail_response = client.get(f"/outputs/{dataset_output['id']}")
    assert output_detail_response.status_code == 200
    output_detail = output_detail_response.json()
    assert output_detail["size_bytes"] == len(b"parquet-data-updated")
    assert output_detail["latest_action"]["id"] == action["id"]
    assert output_detail["latest_action"]["status"] == "succeeded"

    outputs_response = client.get("/outputs", params={"format": "parquet"})
    assert outputs_response.status_code == 200
    refreshed_output = outputs_response.json()[0]
    assert refreshed_output["latest_action"]["id"] == action["id"]
    assert refreshed_output["latest_action"]["action_type"] == "refresh_metadata"


def test_conversion_policy_is_consistent_with_manifest_payload_representation(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_registered_asset(client, monkeypatch, sample_asset_file)

    class FakeConverter:
        def __init__(self, **kwargs):
            self.output_dir = Path(kwargs["output_dir"])

        def convert(self) -> list[Path]:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            dataset_path = self.output_dir / "episode_0001.tfrecord"
            dataset_path.write_bytes(b"tfrecord-data")
            manifest_path = dataset_path.with_suffix(".manifest.json")
            manifest_path.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "episode_id": "episode_0001",
                        "dataset": {
                            "format": "tfrecord",
                            "rows_written": 10,
                            "field_names": ["camera"],
                            "file_size_bytes": len(b"tfrecord-data"),
                        },
                        "source": {
                            "file_path": "/tmp/source.mcap",
                            "ros_version": "ROS2",
                            "storage_format": "mcap",
                        },
                        "temporal": {
                            "duration_seconds": 5.0,
                            "message_count": 10,
                            "start_time_iso": "2026-03-16T10:00:00Z",
                            "end_time_iso": "2026-03-16T10:00:05Z",
                        },
                        "conversion": {
                            "payload_representation": {
                                "image_payload_contract": "bytes_v2",
                                "payload_encoding": "typed_features",
                                "null_encoding": "presence_flag",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            return [dataset_path]

    monkeypatch.setattr(conversion_service, "Converter", FakeConverter)

    conversion_response = client.post(
        "/conversions",
        json={"asset_ids": [asset_id], "output": {"format": "tfrecord"}},
    )
    assert conversion_response.status_code == 201
    conversion = conversion_response.json()

    outputs = client.get("/outputs", params={"conversion_id": conversion["id"]}).json()
    dataset = next(item for item in outputs if item["role"] == "dataset")

    policy_contract = conversion["representation_policy"]["image_payload_contract"]
    manifest_contract = dataset["metadata"]["manifest"]["payload_representation"][
        "image_payload_contract"
    ]

    assert policy_contract == "bytes_v2"
    assert manifest_contract == "bytes_v2"
    assert policy_contract == manifest_contract


def test_output_actions_reject_unsupported_action_type(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    _asset_id, _conversion = create_conversion(client, monkeypatch, sample_asset_file)
    dataset_output = client.get("/outputs", params={"format": "parquet"}).json()[0]

    response = client.post(
        f"/outputs/{dataset_output['id']}/actions",
        json={"action_type": "unsupported_action", "config": {}},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "unsupported output action type: unsupported_action"}
