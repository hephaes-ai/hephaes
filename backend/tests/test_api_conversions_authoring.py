from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.services import conversion_authoring as authoring_service
from hephaes import build_doom_ros_train_py_compatible
from hephaes.conversion.draft_spec import DraftSpecRequest, DraftSpecResult
from hephaes.conversion.introspection import InspectionResult, TopicInspectionResult
from hephaes.conversion.preview import PreviewResult, PreviewRow


def register_asset(client: TestClient, asset_path: Path):
    return client.post("/assets/register", json={"file_path": str(asset_path)})


class FakeReader:
    def __init__(self, *, bag_path: str) -> None:
        self.bag_path = Path(bag_path)
        self.ros_version = "ROS2"
        self.topics = {
            "/camera/front/image_raw": "sensor_msgs/msg/Image",
            "/joy": "sensor_msgs/msg/Joy",
        }

    def read_messages(self, topics=None, on_failure="warn", topic_type_hints=None):
        del topics, on_failure, topic_type_hints
        return iter(())


class ReaderContext(AbstractContextManager[FakeReader]):
    def __init__(self, reader: FakeReader) -> None:
        self.reader = reader

    def __enter__(self) -> FakeReader:
        return self.reader

    def __exit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False


def _install_fake_reader(monkeypatch, *, bag_path: str = "/tmp/fake.mcap") -> FakeReader:
    reader = FakeReader(bag_path=bag_path)
    monkeypatch.setattr(
        authoring_service,
        "open_asset_reader",
        lambda _file_path: ReaderContext(reader),
    )
    return reader


def _build_inspection() -> InspectionResult:
    topic_result = TopicInspectionResult(
        topic="/camera/front/image_raw",
        message_type="sensor_msgs/msg/Image",
        sampled_message_count=2,
        sample_timestamps=[100, 200],
        top_level_summary={"kind": "sample", "preview": {"data": "image"}},
        field_candidates={},
        warnings=[],
    )
    return InspectionResult(
        bag_path="/tmp/fake.mcap",
        ros_version="ROS2",
        sample_n=2,
        topics={topic_result.topic: topic_result},
        warnings=[],
    )


def _build_draft_result() -> DraftSpecResult:
    spec = build_doom_ros_train_py_compatible()
    return DraftSpecResult(
        request=DraftSpecRequest(include_preview=False),
        spec=spec,
        selected_topics=["/camera/front/image_raw", "/joy"],
        trigger_topic="/camera/front/image_raw",
        join_topics=["/joy"],
        warnings=["preview skipped"],
        assumptions=["drafted from inspection"],
        unresolved_fields=[],
        preview=None,
    )


def _build_draft_result_with_preview_bytes() -> DraftSpecResult:
    spec = build_doom_ros_train_py_compatible()
    return DraftSpecResult(
        request=DraftSpecRequest(include_preview=True, preview_rows=2),
        spec=spec,
        selected_topics=["/camera/front/image_raw", "/joy"],
        trigger_topic="/camera/front/image_raw",
        join_topics=["/joy"],
        warnings=[],
        assumptions=["drafted from inspection"],
        unresolved_fields=[],
        preview=_build_preview(),
    )


def _build_preview() -> PreviewResult:
    return PreviewResult(
        rows=[
            PreviewRow(
                timestamp_ns=1,
                field_data={"image": b"\x83\x00"},
                presence_data={"image": 1},
            )
        ],
        checked_records=1,
        bad_records=0,
    )


def test_conversion_authoring_capabilities_route_exposes_backend_contract(client: TestClient):
    response = client.get("/conversions/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["authoring_api_version"] == 1
    assert body["persistence"]["mode"] == "sqlite-json"
    assert body["persistence"]["supports_execute_from_saved_config"] is True
    assert body["hephaes"]["supports_preview"] is True
    assert body["hephaes"]["supports_migration"] is True
    assert body["output_contract"]["policy_version"] == 1
    assert body["output_contract"]["default_image_payload_contract"] == "bytes_v2"
    assert body["output_contract"]["supported_image_payload_contracts"] == ["bytes_v2", "legacy_list_v1"]


def test_conversion_inspection_route_delegates_to_hephaes(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = register_asset(client, sample_asset_file).json()["id"]
    _install_fake_reader(monkeypatch, bag_path=str(sample_asset_file))
    observed: dict[str, Any] = {}

    def fake_inspect_reader(reader, **kwargs):
        observed["reader"] = reader
        observed["kwargs"] = kwargs
        return _build_inspection()

    monkeypatch.setattr(authoring_service, "inspect_reader", fake_inspect_reader)

    response = client.post(
        "/conversions/inspect",
        json={
            "asset_id": asset_id,
            "topics": ["/camera/front/image_raw", "/joy", "/camera/front/image_raw"],
            "sample_n": 2,
            "max_depth": 3,
            "max_sequence_items": 2,
            "topic_type_hints": {"/camera/front/image_raw": "sensor_msgs/msg/Image"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["asset_id"] == asset_id
    assert body["request"]["topics"] == ["/camera/front/image_raw", "/joy"]
    assert body["inspection"]["sample_n"] == 2
    assert body["representation_policy"]["image_payload_contract"] == "bytes_v2"
    assert body["inspection"]["topics"]["/camera/front/image_raw"]["message_type"] == "sensor_msgs/msg/Image"
    assert observed["reader"].topics["/joy"] == "sensor_msgs/msg/Joy"
    assert observed["kwargs"]["topics"] == ["/camera/front/image_raw", "/joy"]
    assert observed["kwargs"]["sample_n"] == 2
    assert observed["kwargs"]["max_depth"] == 3
    assert observed["kwargs"]["max_sequence_items"] == 2
    assert observed["kwargs"]["topic_type_hints"] == {"/camera/front/image_raw": "sensor_msgs/msg/Image"}


def test_conversion_draft_route_delegates_to_hephaes(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = register_asset(client, sample_asset_file).json()["id"]
    _install_fake_reader(monkeypatch, bag_path=str(sample_asset_file))
    observed: dict[str, Any] = {}

    def fake_inspect_reader(reader, **kwargs):
        observed["inspect_reader"] = reader
        observed["inspect_kwargs"] = kwargs
        return _build_inspection()

    def fake_build_draft_conversion_spec(inspection, *, request, reader):
        observed["inspection"] = inspection
        observed["draft_request"] = request
        observed["draft_reader"] = reader
        return _build_draft_result()

    monkeypatch.setattr(authoring_service, "inspect_reader", fake_inspect_reader)
    monkeypatch.setattr(authoring_service, "build_draft_conversion_spec", fake_build_draft_conversion_spec)

    response = client.post(
        "/conversions/draft",
        json={
            "asset_id": asset_id,
            "topics": ["/camera/front/image_raw", "/joy"],
            "sample_n": 2,
            "draft_request": {
                "trigger_topic": "/camera/front/image_raw",
                "selected_topics": ["/camera/front/image_raw", "/joy"],
                "include_preview": False,
                "preview_rows": 2,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["asset_id"] == asset_id
    assert body["request"]["draft_request"]["include_preview"] is False
    assert body["draft"]["spec"]["schema"]["name"] == "doom_ros_train_py_compatible"
    assert body["representation_policy"]["image_payload_contract"] == "bytes_v2"
    assert observed["inspect_reader"].topics["/camera/front/image_raw"] == "sensor_msgs/msg/Image"
    assert observed["inspect_kwargs"]["topics"] == ["/camera/front/image_raw", "/joy"]
    assert observed["draft_request"].selected_topics == ["/camera/front/image_raw", "/joy"]
    assert observed["draft_reader"].bag_path == sample_asset_file.resolve()


def test_conversion_preview_route_delegates_to_hephaes(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = register_asset(client, sample_asset_file).json()["id"]
    _install_fake_reader(monkeypatch, bag_path=str(sample_asset_file))
    observed: dict[str, Any] = {}
    spec = build_doom_ros_train_py_compatible()

    def fake_preview_conversion_spec(reader, conversion_spec, *, sample_n, topic_type_hints):
        observed["reader"] = reader
        observed["spec"] = conversion_spec
        observed["sample_n"] = sample_n
        observed["topic_type_hints"] = topic_type_hints
        return _build_preview()

    monkeypatch.setattr(authoring_service, "preview_conversion_spec", fake_preview_conversion_spec)

    response = client.post(
        "/conversions/preview",
        json={
            "asset_id": asset_id,
            "spec": spec.model_dump(by_alias=True),
            "sample_n": 3,
            "topic_type_hints": {"/camera/front/image_raw": "sensor_msgs/msg/Image"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["asset_id"] == asset_id
    assert body["preview"]["rows"][0]["timestamp_ns"] == 1
    assert body["representation_policy"]["image_payload_contract"] == "bytes_v2"
    assert observed["reader"].topics["/joy"] == "sensor_msgs/msg/Joy"
    assert observed["spec"].schema.name == "doom_ros_train_py_compatible"
    assert observed["sample_n"] == 3
    assert observed["topic_type_hints"] == {"/camera/front/image_raw": "sensor_msgs/msg/Image"}


def test_conversion_draft_route_handles_preview_bytes_payloads(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = register_asset(client, sample_asset_file).json()["id"]
    _install_fake_reader(monkeypatch, bag_path=str(sample_asset_file))

    monkeypatch.setattr(authoring_service, "inspect_reader", lambda _reader, **_kwargs: _build_inspection())
    monkeypatch.setattr(
        authoring_service,
        "build_draft_conversion_spec",
        lambda _inspection, *, request, reader: _build_draft_result_with_preview_bytes(),
    )

    response = client.post(
        "/conversions/draft",
        json={
            "asset_id": asset_id,
            "topics": ["/camera/front/image_raw", "/joy"],
            "sample_n": 2,
            "draft_request": {
                "trigger_topic": "/camera/front/image_raw",
                "selected_topics": ["/camera/front/image_raw", "/joy"],
                "include_preview": True,
                "preview_rows": 2,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["asset_id"] == asset_id
    assert body["draft"]["preview"]["rows"][0]["timestamp_ns"] == 1
    assert body["draft"]["preview"]["rows"][0]["field_data"]["image"]["__bytes__"] is True
    assert body["draft"]["preview"]["rows"][0]["field_data"]["image"]["encoding"] == "base64"
    assert body["draft_revision_id"] is not None

