from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.services import conversions as conversion_service
from app.services import indexing as indexing_service
from hephaes.models import build_doom_ros_train_py_compatible
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


def test_list_conversions_returns_empty_list_initially(client: TestClient):
    response = client.get("/conversions")

    assert response.status_code == 200
    assert response.json() == []


def test_create_conversion_success(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
    backend_outputs_dir: Path,
):
    asset_id = index_registered_asset(client, monkeypatch, sample_asset_file)
    captured: dict[str, object] = {}

    class FakeConverter:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def convert(self) -> list[Path]:
            output_dir = Path(captured["output_dir"])
            output_dir.mkdir(parents=True, exist_ok=True)
            dataset_path = output_dir / "episode_0001.parquet"
            dataset_path.write_bytes(b"parquet-data")
            return [dataset_path]

    monkeypatch.setattr(conversion_service, "Converter", FakeConverter)

    response = client.post(
        "/conversions",
        json={
            "asset_ids": [asset_id],
            "output": {"format": "parquet", "compression": "snappy"},
            "resample": {"freq_hz": 5, "method": "downsample"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["asset_ids"] == [asset_id]
    assert body["config"]["mapping"] == {
        "camera_front_image_raw": ["/camera/front/image_raw"],
        "imu_data": ["/imu/data"],
    }
    assert body["config"]["mapping_mode"] == "auto"
    assert body["config"]["output"] == {"format": "parquet", "compression": "snappy"}
    assert body["config"]["resample"] == {"freq_hz": 5.0, "method": "downsample"}
    assert body["config"]["write_manifest"] is True
    assert body["config"]["spec"]["schema"] == {"name": "legacy_mapping", "version": 1}
    assert body["config"]["spec"]["output"]["format"] == "parquet"
    assert body["config"]["spec"]["output"]["compression"] == "snappy"
    assert body["representation_policy"] == {
        "policy_version": 1,
        "output_format": "parquet",
        "requested_image_payload_contract": None,
        "image_payload_contract": None,
        "payload_encoding": None,
        "null_encoding": None,
        "compatibility_markers": [],
        "warnings": [],
    }
    assert body["output_path"] == str(backend_outputs_dir / "conversions" / body["id"])
    assert body["output_files"] == [str(Path(body["output_path"]) / "episode_0001.parquet")]
    assert body["error_message"] is None
    assert body["job"]["type"] == "convert"
    assert body["job"]["status"] == "succeeded"
    assert body["job"]["target_asset_ids_json"] == [asset_id]
    assert body["job"]["output_path"] == body["output_path"]
    assert body["job"]["error_message"] is None
    assert body["job"]["representation_policy"]["output_format"] == "parquet"
    assert len(captured["file_paths"]) == 1
    assert Path(captured["file_paths"][0]).name == sample_asset_file.name
    assert ".hephaes/imports/" in captured["file_paths"][0]
    assert Path(captured["output_dir"]) == backend_outputs_dir / "conversions" / body["id"]
    assert captured["spec"].schema.name == "legacy_mapping"
    assert captured["spec"].output.compression == "snappy"

    list_response = client.get("/conversions")
    assert list_response.status_code == 200
    assert list_response.json() == [
        {
            "id": body["id"],
            "job_id": body["job_id"],
            "status": "succeeded",
            "asset_ids": [asset_id],
            "config": body["config"],
            "output_path": body["output_path"],
            "error_message": None,
            "representation_policy": body["representation_policy"],
            "created_at": body["created_at"],
            "updated_at": body["updated_at"],
        }
    ]

    detail_response = client.get(f"/conversions/{body['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json() == body


def test_create_conversion_with_spec_payload_uses_richer_conversion_spec(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_registered_asset(client, monkeypatch, sample_asset_file)
    captured: dict[str, object] = {}

    class FakeConverter:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def convert(self) -> list[Path]:
            output_dir = Path(captured["output_dir"])
            output_dir.mkdir(parents=True, exist_ok=True)
            spec = captured["spec"]
            dataset_path = output_dir / f"episode_0001.{spec.output.format}"
            dataset_path.write_bytes(b"spec-dataset")
            return [dataset_path]

    monkeypatch.setattr(conversion_service, "Converter", FakeConverter)

    response = client.post(
        "/conversions",
        json={
            "asset_ids": [asset_id],
            "spec": build_doom_ros_train_py_compatible().model_dump(by_alias=True),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["config"]["mapping_mode"] == "spec"
    assert body["config"]["spec"]["schema"] == {"name": "doom_ros_train_py_compatible", "version": 1}
    assert body["config"]["spec"]["output"]["format"] == "tfrecord"
    assert body["config"]["spec"]["output"]["shards"] == 8
    assert body["representation_policy"] == {
        "policy_version": 1,
        "output_format": "tfrecord",
        "requested_image_payload_contract": "bytes_v2",
        "image_payload_contract": "bytes_v2",
        "payload_encoding": "typed_features",
        "null_encoding": "presence_flag",
        "compatibility_markers": [],
        "warnings": [],
    }
    assert body["output_files"] == [str(Path(body["output_path"]) / "episode_0001.tfrecord")]
    assert captured["spec"].schema.name == "doom_ros_train_py_compatible"
    assert captured["spec"].output.shards == 8
    assert captured["write_manifest"] is True


def test_create_conversion_rejects_unindexed_asset(
    client: TestClient,
    sample_asset_file: Path,
):
    asset_id = register_asset(client, sample_asset_file).json()["id"]

    response = client.post(
        "/conversions",
        json={"asset_ids": [asset_id], "output": {"format": "parquet"}},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": f"asset must be indexed before conversion: {sample_asset_file.name}"
    }


def test_create_conversion_rejects_invalid_spec_contract(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_registered_asset(client, monkeypatch, sample_asset_file)
    spec_payload = build_doom_ros_train_py_compatible().model_dump(by_alias=True)
    spec_payload["output"]["compression"] = "snappy"

    response = client.post(
        "/conversions",
        json={"asset_ids": [asset_id], "spec": spec_payload},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("invalid tfrecord compression" in error["msg"] for error in detail)


def test_create_conversion_rejects_non_tfrecord_legacy_image_contract(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_registered_asset(client, monkeypatch, sample_asset_file)
    spec_payload = build_doom_ros_train_py_compatible().model_dump(by_alias=True)
    spec_payload["output"] = {
        "format": "parquet",
        "compression": "none",
        "image_payload_contract": "legacy_list_v1",
    }

    response = client.post(
        "/conversions",
        json={"asset_ids": [asset_id], "spec": spec_payload},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("image_payload_contract can only be customized" in error["msg"] for error in detail)


def test_create_conversion_with_legacy_image_policy_surfaces_warning(
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
            return [dataset_path]

    monkeypatch.setattr(conversion_service, "Converter", FakeConverter)

    response = client.post(
        "/conversions",
        json={
            "asset_ids": [asset_id],
            "output": {
                "format": "tfrecord",
                "compression": "none",
                "image_payload_contract": "legacy_list_v1",
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["representation_policy"]["requested_image_payload_contract"] == "legacy_list_v1"
    assert body["representation_policy"]["image_payload_contract"] == "legacy_list_v1"
    assert body["representation_policy"]["compatibility_markers"] == ["legacy_list_image_payload"]
    assert body["representation_policy"]["warnings"] == [
        "legacy image payload contract is enabled; image data will remain list-based"
    ]
    assert body["config"]["representation_policy"]["effective_image_payload_contract"] == "legacy_list_v1"


def test_create_conversion_failure_persists_failed_conversion_and_job(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_registered_asset(client, monkeypatch, sample_asset_file)

    class FailingConverter:
        def __init__(self, **_kwargs):
            pass

        def convert(self) -> list[Path]:
            raise RuntimeError("conversion failed")

    monkeypatch.setattr(conversion_service, "Converter", FailingConverter)

    response = client.post(
        "/conversions",
        json={"asset_ids": [asset_id], "output": {"format": "tfrecord", "compression": "gzip"}},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "conversion failed"}

    list_response = client.get("/conversions")
    assert list_response.status_code == 200
    conversions = list_response.json()
    assert len(conversions) == 1
    assert conversions[0]["status"] == "failed"
    assert conversions[0]["asset_ids"] == [asset_id]
    assert conversions[0]["error_message"] == "conversion failed"
    assert conversions[0]["representation_policy"]["output_format"] == "tfrecord"

    detail_response = client.get(f"/conversions/{conversions[0]['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "failed"
    assert detail_response.json()["error_message"] == "conversion failed"
    assert detail_response.json()["job"]["type"] == "convert"
    assert detail_response.json()["job"]["status"] == "failed"
    assert detail_response.json()["job"]["error_message"] == "conversion failed"


def test_get_conversion_returns_404_for_missing_conversion(client: TestClient):
    response = client.get("/conversions/not-a-real-conversion")

    assert response.status_code == 404
    assert response.json() == {"detail": "conversion not found: not-a-real-conversion"}


def test_list_conversions_orders_newest_first(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
):
    first_asset = tmp_path / "one.mcap"
    second_asset = tmp_path / "two.mcap"
    first_asset.write_bytes(b"one")
    second_asset.write_bytes(b"two")

    first_id = index_registered_asset(client, monkeypatch, first_asset)
    second_id = index_registered_asset(client, monkeypatch, second_asset)

    class FakeConverter:
        def __init__(self, **kwargs):
            self.output_dir = Path(kwargs["output_dir"])

        def convert(self) -> list[Path]:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            dataset_path = self.output_dir / "episode_0001.parquet"
            dataset_path.write_bytes(b"parquet-data")
            return [dataset_path]

    monkeypatch.setattr(conversion_service, "Converter", FakeConverter)

    first_response = client.post("/conversions", json={"asset_ids": [first_id], "output": {"format": "parquet"}})
    second_response = client.post("/conversions", json={"asset_ids": [second_id], "output": {"format": "parquet"}})

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    list_response = client.get("/conversions")
    assert list_response.status_code == 200
    assert [item["asset_ids"] for item in list_response.json()] == [[second_id], [first_id]]


def test_list_conversions_can_filter_by_image_payload_contract(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
):
    first_asset = tmp_path / "bytes.mcap"
    second_asset = tmp_path / "legacy.mcap"
    first_asset.write_bytes(b"one")
    second_asset.write_bytes(b"two")

    first_id = index_registered_asset(client, monkeypatch, first_asset)
    second_id = index_registered_asset(client, monkeypatch, second_asset)

    class FakeConverter:
        def __init__(self, **kwargs):
            self.output_dir = Path(kwargs["output_dir"])

        def convert(self) -> list[Path]:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            dataset_path = self.output_dir / "episode_0001.tfrecord"
            dataset_path.write_bytes(b"tfrecord-data")
            return [dataset_path]

    monkeypatch.setattr(conversion_service, "Converter", FakeConverter)

    bytes_response = client.post(
        "/conversions",
        json={"asset_ids": [first_id], "output": {"format": "tfrecord"}},
    )
    legacy_response = client.post(
        "/conversions",
        json={
            "asset_ids": [second_id],
            "output": {
                "format": "tfrecord",
                "image_payload_contract": "legacy_list_v1",
            },
        },
    )

    assert bytes_response.status_code == 201
    assert legacy_response.status_code == 201

    only_bytes = client.get("/conversions", params={"image_payload_contract": "bytes_v2"})
    assert only_bytes.status_code == 200
    assert [item["asset_ids"] for item in only_bytes.json()] == [[first_id]]

    only_legacy = client.get("/conversions", params={"legacy_compatible": "true"})
    assert only_legacy.status_code == 200
    assert [item["asset_ids"] for item in only_legacy.json()] == [[second_id]]
