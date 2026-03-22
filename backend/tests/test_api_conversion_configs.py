from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import ConversionConfig, ConversionDraftRevision
from app.services import conversion_authoring as authoring_service
from app.services import conversions as conversion_service
from app.services import indexing as indexing_service
from hephaes import build_doom_ros_train_py_compatible
from hephaes.conversion.draft_spec import DraftSpecRequest, DraftSpecResult
from hephaes.conversion.introspection import InspectionResult, TopicInspectionResult
from hephaes.conversion.preview import PreviewResult, PreviewRow


def register_asset(client: TestClient, asset_path: Path):
    return client.post("/assets/register", json={"file_path": str(asset_path)})


def build_profile(sample_asset_file: Path, *, topic_name: str = "/camera/front/image_raw"):
    resolved_path = sample_asset_file.resolve()
    start_time = datetime(2026, 3, 16, 10, 0, 0, tzinfo=UTC)
    end_time = datetime(2026, 3, 16, 10, 0, 5, tzinfo=UTC)
    start_timestamp = int(start_time.timestamp() * 1e9)
    end_timestamp = int(end_time.timestamp() * 1e9)

    from hephaes.models import BagMetadata, Topic

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


class ReaderContext:
    def __init__(self, reader: FakeReader) -> None:
        self.reader = reader

    def __enter__(self) -> FakeReader:
        return self.reader

    def __exit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False


def _install_fake_reader(monkeypatch, *, bag_path: str) -> FakeReader:
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
        preview=PreviewResult(
            rows=[
                PreviewRow(
                    timestamp_ns=1,
                    field_data={"image": b"\x00\x01"},
                    presence_data={"image": 1},
                )
            ],
            checked_records=1,
            bad_records=0,
        ),
    )


def install_fake_converter(monkeypatch) -> None:
    class FakeConverter:
        def __init__(self, **kwargs):
            self.output_dir = Path(kwargs["output_dir"])

        def convert(self) -> list[Path]:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            dataset_path = self.output_dir / "episode_0001.parquet"
            dataset_path.write_bytes(b"parquet-data")
            return [dataset_path]

    monkeypatch.setattr(conversion_service, "Converter", FakeConverter)


def test_saved_config_crud_duplicate_and_execute_from_saved_config(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    spec = build_doom_ros_train_py_compatible()
    create_response = client.post(
        "/conversion-configs",
        json={
            "name": "  Demo Config  ",
            "description": "  reusable config  ",
            "metadata": {"owner": "qa"},
            "spec": spec.model_dump(by_alias=True),
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    config_id = created["id"]
    assert created["name"] == "Demo Config"
    assert created["status"] == "ready"
    assert created["spec_schema_name"] == "doom_ros_train_py_compatible"
    assert created["revision_count"] == 1
    assert created["draft_count"] == 0

    list_response = client.get("/conversion-configs")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [config_id]

    detail_response = client.get(f"/conversion-configs/{config_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["resolved_spec_document"]["spec_version"] == 2
    assert detail["revisions"][0]["change_kind"] == "create"

    update_response = client.patch(
        f"/conversion-configs/{config_id}",
        json={"name": "  Renamed Config  ", "metadata": {"owner": "platform"}},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "Renamed Config"
    assert updated["revision_count"] == 2
    assert updated["metadata"] == {"owner": "platform"}

    duplicate_response = client.post(
        f"/conversion-configs/{config_id}/duplicate",
        json={"description": "copy"},
    )
    assert duplicate_response.status_code == 201
    duplicate = duplicate_response.json()
    assert duplicate["id"] != config_id
    assert duplicate["name"].startswith("Copy of Renamed Config")
    assert duplicate["revision_count"] == 1

    asset_id = index_registered_asset(client, monkeypatch, sample_asset_file)
    install_fake_converter(monkeypatch)

    conversion_response = client.post(
        "/conversions",
        json={"asset_ids": [asset_id], "saved_config_id": config_id},
    )

    assert conversion_response.status_code == 201
    conversion = conversion_response.json()
    assert conversion["config"]["saved_config_id"] == config_id
    assert conversion["config"]["mapping_mode"] == "saved-config"
    assert conversion["config"]["saved_config_revision_number"] == 2
    assert conversion["config"]["saved_config_spec_document_version"] == 2
    assert conversion["job"]["config_json"]["saved_config_id"] == config_id


def test_saved_config_migrates_on_load_and_persists_revision(
    client: TestClient,
):
    spec = build_doom_ros_train_py_compatible()
    create_response = client.post(
        "/conversion-configs",
        json={
            "name": "Migration Config",
            "spec": spec.model_dump(by_alias=True),
        },
    )
    assert create_response.status_code == 201
    config_id = create_response.json()["id"]

    session = client.app.state.session_factory()
    try:
        config = session.scalar(select(ConversionConfig).where(ConversionConfig.id == config_id))
        assert config is not None
        config.spec_document_json = {**config.spec_document_json, "spec_version": 1}
        config.spec_document_version = 1
        config.migration_notes_json = []
        config.invalid_reason = None
        session.commit()
    finally:
        session.close()

    detail_response = client.get(f"/conversion-configs/{config_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "ready"
    assert detail["resolved_spec_document"]["spec_version"] == 2
    assert any("migrate" in note for note in detail["migration_notes"])
    assert detail["revision_count"] == 2

    session = client.app.state.session_factory()
    try:
        config = session.scalar(select(ConversionConfig).where(ConversionConfig.id == config_id))
        assert config is not None
        assert config.spec_document_version == 2
        assert config.current_revision_number == 2
        assert len(config.revisions) == 2
    finally:
        session.close()


def test_conversion_draft_route_persists_draft_revision(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = register_asset(client, sample_asset_file).json()["id"]
    _install_fake_reader(monkeypatch, bag_path=str(sample_asset_file))
    observed: dict[str, object] = {}

    def fake_inspect_reader(reader, **kwargs):
        observed["reader"] = reader
        observed["kwargs"] = kwargs
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
                "include_preview": True,
                "preview_rows": 1,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["draft_revision_id"] is not None
    assert body["draft"]["spec"]["schema"]["name"] == "doom_ros_train_py_compatible"

    session = client.app.state.session_factory()
    try:
        draft_rows = session.scalars(select(ConversionDraftRevision)).all()
        assert len(draft_rows) == 1
        draft_row = draft_rows[0]
        assert draft_row.id == body["draft_revision_id"]
        assert draft_row.status == "draft"
        assert draft_row.saved_config_id is None
        assert draft_row.source_asset_id == asset_id
        assert draft_row.preview_json is not None
    finally:
        session.close()

