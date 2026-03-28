from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hephaes import (
    AssetAlreadyRegisteredError,
    AssetNotFoundError,
    AssetReadError,
    ConversionConfigAlreadyExistsError,
    ConversionDraftConfirmationError,
    ConversionDraftNotFoundError,
    ConversionDraftRevisionNotFoundError,
    ConversionDraftStateError,
    DraftSpecRequest,
    InspectionRequest,
    InvalidAssetPathError,
    TagAlreadyExistsError,
    Workspace,
    WorkspaceAlreadyExistsError,
    WorkspaceNotFoundError,
)
from hephaes.conversion.spec_io import build_conversion_spec_document, dump_conversion_spec_document
from hephaes.workspace.schema import migrate_workspace_schema, WORKSPACE_SCHEMA_VERSION
from hephaes.models import BagMetadata, Message, Topic
from hephaes.models import ConversionSpec, OutputSpec, SchemaSpec


class FakeWorkspaceAuthoringReader:
    def __init__(
        self,
        *,
        bag_path: str = "/tmp/test.mcap",
        ros_version: str = "ROS2",
        fail_on_read: bool = False,
    ) -> None:
        self.bag_path = Path(bag_path)
        self.ros_version = ros_version
        self.fail_on_read = fail_on_read
        self.topics = {
            "/doom_image": "custom_msgs/msg/RawImageBGRA",
            "/joy": "sensor_msgs/msg/Joy",
        }
        self._messages = [
            Message(timestamp=90, topic="/joy", data={"buttons": [1, 0, 0] + [0] * 12, "axes": [0.0, 0.5]}),
            Message(timestamp=100, topic="/doom_image", data={"data": bytes(range(16))}),
            Message(timestamp=190, topic="/joy", data={"buttons": [0, 1, 0] + [0] * 12, "axes": [0.25, -0.25]}),
            Message(timestamp=200, topic="/doom_image", data={"data": bytes(range(16, 32))}),
        ]

    def read_messages(
        self,
        topics=None,
        *,
        on_failure="warn",
        topic_type_hints=None,
        start_ns=None,
        stop_ns=None,
    ):
        del on_failure, topic_type_hints, start_ns, stop_ns
        if self.fail_on_read:
            raise RuntimeError("reader exploded")
        topic_filter = set(topics) if topics else None
        for message in self._messages:
            if topic_filter is not None and message.topic not in topic_filter:
                continue
            yield message

    def close(self) -> None:
        return None


def test_workspace_init_creates_layout(tmp_path: Path) -> None:
    workspace = Workspace.init(tmp_path)

    assert workspace.root == tmp_path
    assert (tmp_path / ".hephaes").is_dir()
    assert (tmp_path / ".hephaes" / "workspace.sqlite3").is_file()
    assert (tmp_path / ".hephaes" / "imports").is_dir()
    assert (tmp_path / ".hephaes" / "outputs").is_dir()
    assert (tmp_path / ".hephaes" / "specs").is_dir()
    assert (tmp_path / ".hephaes" / "specs" / "revisions").is_dir()
    assert (tmp_path / ".hephaes" / "specs" / "drafts").is_dir()
    assert (tmp_path / ".hephaes" / "jobs").is_dir()


def test_workspace_init_rejects_duplicate_without_exist_ok(tmp_path: Path) -> None:
    Workspace.init(tmp_path)

    with pytest.raises(WorkspaceAlreadyExistsError):
        Workspace.init(tmp_path)


def test_workspace_open_resolves_parent_workspace(tmp_path: Path) -> None:
    Workspace.init(tmp_path)
    nested_dir = tmp_path / "nested" / "child"
    nested_dir.mkdir(parents=True)

    workspace = Workspace.open(nested_dir)

    assert workspace.root == tmp_path


def test_workspace_open_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceNotFoundError):
        Workspace.open(tmp_path)


def test_register_asset_persists_across_reopen(tmp_path: Path, tmp_mcap_file: Path) -> None:
    workspace = Workspace.init(tmp_path)

    registered = workspace.register_asset(tmp_mcap_file)
    reopened = Workspace.open(tmp_path)
    assets = reopened.list_assets()

    assert len(assets) == 1
    assert assets[0].id == registered.id
    assert Path(assets[0].file_path).is_file()
    assert str(tmp_path / ".hephaes" / "imports") in assets[0].file_path
    assert assets[0].source_path == str(tmp_mcap_file.resolve())
    assert assets[0].file_type == "mcap"
    assert assets[0].indexing_status == "pending"


def test_register_asset_rejects_duplicates_by_default(tmp_path: Path, tmp_bag_file: Path) -> None:
    workspace = Workspace.init(tmp_path)
    workspace.register_asset(tmp_bag_file)

    with pytest.raises(AssetAlreadyRegisteredError):
        workspace.register_asset(tmp_bag_file)


def test_register_asset_supports_duplicate_skip(tmp_path: Path, tmp_bag_file: Path) -> None:
    workspace = Workspace.init(tmp_path)
    first = workspace.register_asset(tmp_bag_file)
    second = workspace.register_asset(tmp_bag_file, on_duplicate="skip")

    assert second.id == first.id
    assert len(workspace.list_assets()) == 1


def test_register_asset_supports_duplicate_refresh(tmp_path: Path, tmp_bag_file: Path) -> None:
    workspace = Workspace.init(tmp_path)
    first = workspace.register_asset(tmp_bag_file)
    tmp_bag_file.write_bytes(b"12345")

    refreshed = workspace.register_asset(tmp_bag_file, on_duplicate="refresh")

    assert refreshed.id == first.id
    assert refreshed.file_size == 5
    assert refreshed.updated_at >= first.updated_at


def test_import_asset_copies_file_into_workspace(tmp_path: Path, tmp_bag_file: Path) -> None:
    workspace = Workspace.init(tmp_path)

    asset = workspace.import_asset(tmp_bag_file)

    imported_path = Path(asset.file_path)
    assert imported_path.is_file()
    assert imported_path.read_bytes() == tmp_bag_file.read_bytes()
    assert imported_path.parent.parent == tmp_path / ".hephaes" / "imports"
    assert asset.source_path == str(tmp_bag_file.resolve())


def test_create_and_list_tags(tmp_path: Path) -> None:
    workspace = Workspace.init(tmp_path)

    created = workspace.create_tag("Priority")
    tags = workspace.list_tags()

    assert len(tags) == 1
    assert tags[0].id == created.id
    assert tags[0].name == "Priority"


def test_create_tag_rejects_duplicate_names(tmp_path: Path) -> None:
    workspace = Workspace.init(tmp_path)
    workspace.create_tag("Priority")

    with pytest.raises(TagAlreadyExistsError):
        workspace.create_tag(" priority ")


def test_attach_and_filter_assets_by_tags(tmp_path: Path, tmp_bag_file: Path, tmp_mcap_file: Path) -> None:
    workspace = Workspace.init(tmp_path)
    bag_asset = workspace.register_asset(tmp_bag_file)
    mcap_asset = workspace.register_asset(tmp_mcap_file)
    priority = workspace.create_tag("Priority")
    workspace.create_tag("Review")

    workspace.attach_tag_to_asset(bag_asset.id, priority.id)

    priority_assets = workspace.list_assets(tags=["priority"])
    all_assets = workspace.list_assets()
    bag_tags = workspace.get_asset_tags(bag_asset.id)
    mcap_tags = workspace.get_asset_tags(mcap_asset.id)

    assert [asset.id for asset in priority_assets] == [bag_asset.id]
    assert {asset.id for asset in all_assets} == {bag_asset.id, mcap_asset.id}
    assert [tag.name for tag in bag_tags] == ["Priority"]
    assert mcap_tags == []


def test_remove_tag_from_asset(tmp_path: Path, tmp_bag_file: Path) -> None:
    workspace = Workspace.init(tmp_path)
    asset = workspace.register_asset(tmp_bag_file)
    tag = workspace.create_tag("Priority")
    workspace.attach_tag_to_asset(asset.id, tag.id)

    workspace.remove_tag_from_asset(asset.id, tag.id)

    assert workspace.get_asset_tags(asset.id) == []


def test_register_asset_rejects_unsupported_types(tmp_path: Path) -> None:
    workspace = Workspace.init(tmp_path)
    unsupported = tmp_path / "notes.txt"
    unsupported.write_text("hello", encoding="utf-8")

    with pytest.raises(InvalidAssetPathError):
        workspace.register_asset(unsupported)


def test_index_asset_persists_profiled_metadata(
    tmp_path: Path,
    tmp_mcap_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = Workspace.init(tmp_path)
    asset = workspace.register_asset(tmp_mcap_file)

    def fake_profile_asset_file(file_path: str, *, max_workers: int = 1) -> BagMetadata:
        assert Path(file_path).is_file()
        assert Path(file_path).name == tmp_mcap_file.name
        assert str(tmp_path / ".hephaes" / "imports") in file_path
        assert max_workers == 1
        return BagMetadata(
            path=file_path,
            file_path=file_path,
            ros_version="ROS2",
            storage_format="mcap",
            file_size_bytes=123,
            start_timestamp=1_000_000_000,
            end_timestamp=3_000_000_000,
            start_time_iso="1970-01-01T00:00:01+00:00",
            end_time_iso="1970-01-01T00:00:03+00:00",
            duration_seconds=2.0,
            message_count=42,
            topics=[
                Topic(
                    name="/camera/image",
                    message_type="sensor_msgs/Image",
                    message_count=20,
                    rate_hz=10.0,
                ),
                Topic(
                    name="/imu/data",
                    message_type="sensor_msgs/Imu",
                    message_count=22,
                    rate_hz=11.0,
                ),
            ],
            compression_format="none",
        )

    monkeypatch.setattr("hephaes.workspace.profile_asset_file", fake_profile_asset_file)

    indexed_asset = workspace.index_asset(asset.id)
    metadata = workspace.get_asset_metadata(asset.id)

    assert indexed_asset.indexing_status == "indexed"
    assert indexed_asset.last_indexed_at is not None
    assert metadata is not None
    assert metadata.duration == 2.0
    assert metadata.message_count == 42
    assert metadata.topic_count == 2
    assert metadata.sensor_types == ["camera", "imu"]
    assert metadata.indexing_error is None
    assert metadata.default_episode is not None
    assert metadata.default_episode.episode_id == f"{asset.id}:default"
    assert metadata.visualization_summary is not None
    assert metadata.visualization_summary.has_visualizable_streams is True
    assert metadata.visualization_summary.default_lane_count == 2
    assert metadata.raw_metadata.storage_format == "mcap"
    assert len(metadata.topics) == 2
    assert metadata.topics[0].name == "/camera/image"

    reopened = Workspace.open(tmp_path)
    reopened_metadata = reopened.get_asset_metadata(asset.id)
    assert reopened_metadata is not None
    assert reopened_metadata.message_count == 42
    jobs = reopened.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].kind == "index_asset"
    assert jobs[0].status == "succeeded"
    assert jobs[0].target_asset_ids == [asset.id]


def test_index_asset_persists_failure_state(
    tmp_path: Path,
    tmp_bag_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = Workspace.init(tmp_path)
    asset = workspace.register_asset(tmp_bag_file)

    def fake_profile_asset_file(file_path: str, *, max_workers: int = 1) -> BagMetadata:
        raise RuntimeError("boom")

    monkeypatch.setattr("hephaes.workspace.profile_asset_file", fake_profile_asset_file)

    with pytest.raises(RuntimeError, match="boom"):
        workspace.index_asset(asset.id)

    failed_asset = workspace.get_asset_or_raise(asset.id)
    metadata = workspace.get_asset_metadata(asset.id)

    assert failed_asset.indexing_status == "failed"
    assert failed_asset.last_indexed_at is None
    assert metadata is not None
    assert metadata.indexing_error == "boom"
    assert metadata.message_count == 0
    jobs = workspace.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].status == "failed"
    assert jobs[0].error_message == "boom"


def test_reindex_failure_preserves_previous_metadata(
    tmp_path: Path,
    tmp_mcap_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = Workspace.init(tmp_path)
    asset = workspace.register_asset(tmp_mcap_file)

    def successful_profile(file_path: str, *, max_workers: int = 1) -> BagMetadata:
        return BagMetadata(
            path=file_path,
            file_path=file_path,
            ros_version="ROS2",
            storage_format="mcap",
            file_size_bytes=123,
            start_timestamp=1_000_000_000,
            end_timestamp=3_000_000_000,
            start_time_iso="1970-01-01T00:00:01+00:00",
            end_time_iso="1970-01-01T00:00:03+00:00",
            duration_seconds=2.0,
            message_count=42,
            topics=[
                Topic(
                    name="/camera/image",
                    message_type="sensor_msgs/Image",
                    message_count=20,
                    rate_hz=10.0,
                )
            ],
            compression_format="none",
        )

    monkeypatch.setattr("hephaes.workspace.profile_asset_file", successful_profile)
    workspace.index_asset(asset.id)
    first_metadata = workspace.get_asset_metadata(asset.id)
    assert first_metadata is not None

    def failing_profile(file_path: str, *, max_workers: int = 1) -> BagMetadata:
        raise RuntimeError("reindex failed")

    monkeypatch.setattr("hephaes.workspace.profile_asset_file", failing_profile)

    with pytest.raises(RuntimeError, match="reindex failed"):
        workspace.index_asset(asset.id)

    preserved_metadata = workspace.get_asset_metadata(asset.id)
    failed_asset = workspace.get_asset_or_raise(asset.id)

    assert preserved_metadata is not None
    assert preserved_metadata.message_count == 42
    assert preserved_metadata.topic_count == 1
    assert preserved_metadata.sensor_types == ["camera"]
    assert preserved_metadata.raw_metadata.storage_format == "mcap"
    assert preserved_metadata.indexing_error == "reindex failed"
    assert failed_asset.indexing_status == "failed"


def test_index_asset_raises_for_missing_asset(tmp_path: Path) -> None:
    workspace = Workspace.init(tmp_path)

    with pytest.raises(AssetNotFoundError):
        workspace.index_asset("missing")


def test_save_and_list_conversion_configs(tmp_path: Path) -> None:
    workspace = Workspace.init(tmp_path)
    spec = ConversionSpec(
        schema=SchemaSpec(name="demo", version=1),
        output=OutputSpec(format="parquet"),
    )

    saved = workspace.save_conversion_config(
        name="Demo Config",
        spec_document=build_conversion_spec_document(spec, metadata={"source": "test"}),
        description="example",
    )
    configs = workspace.list_saved_conversion_configs()
    resolved = workspace.resolve_saved_conversion_config(saved.id)

    assert len(configs) == 1
    assert configs[0].id == saved.id
    assert configs[0].name == "Demo Config"
    assert configs[0].description == "example"
    assert Path(configs[0].document_path).is_file()
    assert resolved.document.spec.schema.name == "demo"
    assert resolved.metadata == {"source": "test"}


def test_save_conversion_config_rejects_duplicate_names(tmp_path: Path) -> None:
    workspace = Workspace.init(tmp_path)
    spec = ConversionSpec(
        schema=SchemaSpec(name="demo", version=1),
        output=OutputSpec(format="parquet"),
    )
    document = build_conversion_spec_document(spec)

    workspace.save_conversion_config(name="Demo Config", spec_document=document)

    with pytest.raises(ConversionConfigAlreadyExistsError):
        workspace.save_conversion_config(name="demo   config", spec_document=document)


def test_resolve_saved_conversion_config_by_name(tmp_path: Path) -> None:
    workspace = Workspace.init(tmp_path)
    spec = ConversionSpec(
        schema=SchemaSpec(name="demo", version=1),
        output=OutputSpec(format="tfrecord"),
    )
    workspace.save_conversion_config(name="TF Config", spec_document=build_conversion_spec_document(spec))

    resolved = workspace.resolve_saved_conversion_config("tf config")

    assert resolved.name == "TF Config"
    assert resolved.document.spec.output.format == "tfrecord"


def test_update_saved_conversion_config_creates_revision(tmp_path: Path) -> None:
    workspace = Workspace.init(tmp_path)
    original_spec = ConversionSpec(
        schema=SchemaSpec(name="demo", version=1),
        output=OutputSpec(format="parquet"),
    )
    saved = workspace.save_conversion_config(
        name="Demo Config",
        spec_document=build_conversion_spec_document(original_spec, metadata={"stage": "initial"}),
        description="first",
    )
    updated_spec = ConversionSpec(
        schema=SchemaSpec(name="demo_updated", version=2),
        output=OutputSpec(format="tfrecord"),
    )

    updated = workspace.update_saved_conversion_config(
        saved.id,
        spec_document=build_conversion_spec_document(updated_spec, metadata={"stage": "updated"}),
        name="Demo Config v2",
        description="second",
    )
    revisions = workspace.list_saved_conversion_config_revisions(saved.id)

    assert updated.id == saved.id
    assert updated.name == "Demo Config v2"
    assert updated.description == "second"
    assert updated.document.spec.schema.name == "demo_updated"
    assert updated.metadata == {"stage": "updated"}
    assert [revision.revision_number for revision in revisions] == [2, 1]
    latest_revision = workspace.get_saved_conversion_config_revision(revisions[0].id)
    assert latest_revision is not None
    assert latest_revision.document.spec.output.format == "tfrecord"
    assert latest_revision.metadata == {"stage": "updated"}


def test_duplicate_saved_conversion_config_creates_new_config(tmp_path: Path) -> None:
    workspace = Workspace.init(tmp_path)
    spec = ConversionSpec(
        schema=SchemaSpec(name="demo", version=1),
        output=OutputSpec(format="parquet"),
    )
    saved = workspace.save_conversion_config(
        name="Demo Config",
        spec_document=build_conversion_spec_document(spec),
    )

    duplicate = workspace.duplicate_saved_conversion_config(saved.id, name="Demo Config Copy")
    duplicate_revisions = workspace.list_saved_conversion_config_revisions(duplicate.id)

    assert duplicate.id != saved.id
    assert duplicate.name == "Demo Config Copy"
    assert duplicate.document.spec.schema.name == "demo"
    assert [revision.revision_number for revision in duplicate_revisions] == [1]


def test_record_and_list_conversion_draft_revisions(tmp_path: Path, tmp_mcap_file: Path) -> None:
    workspace = Workspace.init(tmp_path)
    asset = workspace.register_asset(tmp_mcap_file)
    spec = ConversionSpec(
        schema=SchemaSpec(name="draft_demo", version=1),
        output=OutputSpec(format="parquet"),
    )
    saved = workspace.save_conversion_config(
        name="Draft Config",
        spec_document=build_conversion_spec_document(spec),
    )

    draft = workspace.record_conversion_draft_revision(
        label="Draft 1",
        saved_config_selector=saved.id,
        source_asset_selector=asset.id,
        spec_document=build_conversion_spec_document(spec, metadata={"draft": True}),
        inspection_request={"asset_id": asset.id, "sample_n": 2},
        inspection={"bag_path": str(tmp_mcap_file), "sample_n": 2, "topics": {}, "warnings": []},
        draft_request={"include_preview": True},
        draft_result={"selected_topics": [], "warnings": [], "assumptions": [], "unresolved_fields": []},
        preview={"rows": [], "checked_records": 0, "bad_records": 0},
    )
    drafts = workspace.list_conversion_draft_revisions(saved_config_selector=saved.id)
    resolved = workspace.get_conversion_draft_revision(draft.id)

    assert len(drafts) == 1
    assert drafts[0].id == draft.id
    assert drafts[0].revision_number == 1
    assert drafts[0].draft_id is not None
    assert drafts[0].saved_config_id == saved.id
    assert drafts[0].source_asset_id == asset.id
    assert drafts[0].status == "saved"
    assert drafts[0].inspection_request_json == {"asset_id": asset.id, "sample_n": 2}
    assert drafts[0].preview_request_json == {}
    assert resolved is not None
    assert resolved.draft_id == drafts[0].draft_id
    assert resolved.label == "Draft 1"
    assert resolved.revision_number == 1
    assert resolved.status == "saved"
    assert resolved.metadata == {"draft": True}
    assert resolved.preview_request_json == {}
    assert resolved.preview_json == {"rows": [], "checked_records": 0, "bad_records": 0}

    with sqlite3.connect(workspace.database_path) as connection:
        connection.row_factory = sqlite3.Row
        draft_row = connection.execute(
            "SELECT * FROM conversion_drafts WHERE id = ?",
            (drafts[0].draft_id,),
        ).fetchone()

    assert draft_row is not None
    assert draft_row["source_asset_id"] == asset.id
    assert draft_row["status"] == "saved"
    assert draft_row["current_revision_id"] == draft.id
    assert draft_row["confirmed_revision_id"] == draft.id
    assert draft_row["saved_config_id"] == saved.id


def test_list_and_resolve_conversion_drafts(
    tmp_path: Path,
    tmp_mcap_file: Path,
    tmp_bag_file: Path,
) -> None:
    workspace = Workspace.init(tmp_path)
    first_asset = workspace.register_asset(tmp_mcap_file)
    second_asset = workspace.register_asset(tmp_bag_file)
    spec = ConversionSpec(
        schema=SchemaSpec(name="draft_listing_demo", version=1),
        output=OutputSpec(format="parquet"),
    )
    saved = workspace.save_conversion_config(
        name="Draft Listing Config",
        spec_document=build_conversion_spec_document(spec),
    )

    saved_revision = workspace.record_conversion_draft_revision(
        label="Saved Draft",
        saved_config_selector=saved.id,
        source_asset_selector=first_asset.id,
        spec_document=build_conversion_spec_document(spec, metadata={"kind": "saved"}),
    )
    draft_revision = workspace.record_conversion_draft_revision(
        label="Working Draft",
        source_asset_selector=second_asset.id,
        spec_document=build_conversion_spec_document(spec, metadata={"kind": "draft"}),
    )

    all_drafts = workspace.list_conversion_drafts()
    saved_drafts = workspace.list_conversion_drafts(status="saved")
    working_drafts = workspace.list_conversion_drafts(status="draft")
    second_asset_drafts = workspace.list_conversion_drafts(
        source_asset_selector=second_asset.id
    )
    config_drafts = workspace.list_conversion_drafts(saved_config_selector=saved.id)
    resolved = workspace.resolve_conversion_draft(draft_revision.draft_id or "")

    assert {draft.id for draft in all_drafts} == {
        saved_revision.draft_id,
        draft_revision.draft_id,
    }
    assert [draft.id for draft in saved_drafts] == [saved_revision.draft_id]
    assert [draft.id for draft in working_drafts] == [draft_revision.draft_id]
    assert [draft.id for draft in second_asset_drafts] == [draft_revision.draft_id]
    assert [draft.id for draft in config_drafts] == [saved_revision.draft_id]
    assert resolved.id == draft_revision.draft_id
    assert resolved.source_asset_id == second_asset.id
    assert resolved.status == "draft"
    assert resolved.current_revision is not None
    assert resolved.current_revision.id == draft_revision.id
    assert resolved.current_revision.metadata == {"kind": "draft"}
    assert resolved.confirmed_revision is None

    with pytest.raises(ConversionDraftNotFoundError):
        workspace.resolve_conversion_draft("missing-draft")


def test_list_conversion_draft_revisions_filters_by_draft_selector(
    tmp_path: Path,
    tmp_mcap_file: Path,
) -> None:
    workspace = Workspace.init(tmp_path)
    asset = workspace.register_asset(tmp_mcap_file)
    spec_v1 = build_conversion_spec_document(
        ConversionSpec(
            schema=SchemaSpec(name="draft_revision_demo", version=1),
            output=OutputSpec(format="parquet"),
        ),
        metadata={"revision": 1},
    )
    spec_v2 = build_conversion_spec_document(
        ConversionSpec(
            schema=SchemaSpec(name="draft_revision_demo_v2", version=2),
            output=OutputSpec(format="parquet"),
        ),
        metadata={"revision": 2},
    )
    timestamp = datetime.now(timezone.utc)

    with workspace._transaction() as connection:
        draft = workspace._create_conversion_draft(
            connection,
            source_asset_id=asset.id,
            status="draft",
            saved_config_id=None,
            timestamp=timestamp,
        )
        revision_one = workspace._append_conversion_draft_revision(
            connection,
            draft_id=draft.id,
            spec_document=spec_v1,
            label="Revision 1",
            saved_config_id=None,
            source_asset_id=asset.id,
            status="draft",
            inspection_request={"sample_n": 2},
            inspection={"topics": {}},
            draft_request={"strategy": "initial"},
            draft_result={"warnings": []},
            preview_request={},
            preview=None,
            timestamp=timestamp,
        )
        workspace._set_conversion_draft_current_revision(
            draft.id,
            revision_one.id,
            connection=connection,
            timestamp=timestamp,
        )
        revision_two = workspace._append_conversion_draft_revision(
            connection,
            draft_id=draft.id,
            spec_document=spec_v2,
            label="Revision 2",
            saved_config_id=None,
            source_asset_id=asset.id,
            status="draft",
            inspection_request={"sample_n": 4},
            inspection={"topics": {"demo": {}}},
            draft_request={"strategy": "refined"},
            draft_result={"warnings": ["topic filtered"]},
            preview_request={"limit": 5},
            preview={"rows": [], "checked_records": 0, "bad_records": 0},
            timestamp=timestamp,
        )
        workspace._set_conversion_draft_current_revision(
            draft.id,
            revision_two.id,
            connection=connection,
            timestamp=timestamp,
        )

        other_draft = workspace._create_conversion_draft(
            connection,
            source_asset_id=None,
            status="draft",
            saved_config_id=None,
            timestamp=timestamp,
        )
        other_revision = workspace._append_conversion_draft_revision(
            connection,
            draft_id=other_draft.id,
            spec_document=spec_v1,
            label="Other Revision",
            saved_config_id=None,
            source_asset_id=None,
            status="draft",
            inspection_request={},
            inspection={},
            draft_request={},
            draft_result={},
            preview_request={},
            preview=None,
            timestamp=timestamp,
        )
        workspace._set_conversion_draft_current_revision(
            other_draft.id,
            other_revision.id,
            connection=connection,
            timestamp=timestamp,
        )

    revisions = workspace.list_conversion_draft_revisions(draft_selector=draft.id)
    resolved = workspace.resolve_conversion_draft(draft.id)

    assert [revision.id for revision in revisions] == [revision_two.id, revision_one.id]
    assert [revision.revision_number for revision in revisions] == [2, 1]
    assert all(revision.draft_id == draft.id for revision in revisions)
    assert resolved.current_revision is not None
    assert resolved.current_revision.id == revision_two.id
    assert resolved.current_revision.preview_request_json == {"limit": 5}
    assert resolved.current_revision.preview_json == {
        "rows": [],
        "checked_records": 0,
        "bad_records": 0,
    }
    assert resolved.confirmed_revision is None


def test_conversion_draft_primitives_validate_state_and_revision_membership(
    tmp_path: Path,
    tmp_mcap_file: Path,
) -> None:
    workspace = Workspace.init(tmp_path)
    asset = workspace.register_asset(tmp_mcap_file)
    spec = build_conversion_spec_document(
        ConversionSpec(
            schema=SchemaSpec(name="draft_state_demo", version=1),
            output=OutputSpec(format="parquet"),
        )
    )
    timestamp = datetime.now(timezone.utc)

    with workspace._transaction() as connection:
        first_draft = workspace._create_conversion_draft(
            connection,
            source_asset_id=asset.id,
            status="draft",
            saved_config_id=None,
            timestamp=timestamp,
        )
        first_revision = workspace._append_conversion_draft_revision(
            connection,
            draft_id=first_draft.id,
            spec_document=spec,
            label="First Revision",
            saved_config_id=None,
            source_asset_id=asset.id,
            status="draft",
            inspection_request={},
            inspection={},
            draft_request={},
            draft_result={},
            preview_request={},
            preview=None,
            timestamp=timestamp,
        )
        workspace._set_conversion_draft_current_revision(
            first_draft.id,
            first_revision.id,
            connection=connection,
            timestamp=timestamp,
        )

        second_draft = workspace._create_conversion_draft(
            connection,
            source_asset_id=None,
            status="draft",
            saved_config_id=None,
            timestamp=timestamp,
        )
        second_revision = workspace._append_conversion_draft_revision(
            connection,
            draft_id=second_draft.id,
            spec_document=spec,
            label="Second Revision",
            saved_config_id=None,
            source_asset_id=None,
            status="draft",
            inspection_request={},
            inspection={},
            draft_request={},
            draft_result={},
            preview_request={},
            preview=None,
            timestamp=timestamp,
        )
        workspace._set_conversion_draft_current_revision(
            second_draft.id,
            second_revision.id,
            connection=connection,
            timestamp=timestamp,
        )

    with pytest.raises(ConversionDraftRevisionNotFoundError):
        workspace._get_conversion_draft_revision_summary_or_raise("missing-revision")

    with pytest.raises(ConversionDraftStateError):
        workspace._set_conversion_draft_current_revision(first_draft.id, second_revision.id)

    with pytest.raises(ConversionDraftStateError):
        workspace._set_conversion_draft_confirmed_revision(first_draft.id, second_revision.id)

    workspace._set_conversion_draft_status(first_draft.id, "discarded")
    discarded = workspace.resolve_conversion_draft(first_draft.id)

    assert discarded.status == "discarded"
    assert discarded.discarded_at is not None

    with pytest.raises(ConversionDraftStateError):
        workspace._set_conversion_draft_status(first_draft.id, "draft")


def test_workspace_inspect_asset_and_create_conversion_draft(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    tmp_mcap_file: Path,
) -> None:
    workspace = Workspace.init(tmp_path)
    asset = workspace.register_asset(tmp_mcap_file)
    monkeypatch.setattr(
        "hephaes.workspace.drafts.RosReader.open",
        lambda bag_path, ros_version=None, registry=None: FakeWorkspaceAuthoringReader(
            bag_path=bag_path,
        ),
    )

    inspection = workspace.inspect_asset(
        asset.id,
        request=InspectionRequest(sample_n=2, topics=["/doom_image", "/joy"]),
    )
    draft = workspace.create_conversion_draft(
        asset.id,
        inspection_request={"sample_n": 2, "topics": ["/doom_image", "/joy"]},
        draft_request=DraftSpecRequest(
            trigger_topic="/doom_image",
            selected_topics=["/doom_image", "/joy"],
            max_features_per_topic=1,
            label_feature="buttons",
            include_preview=False,
        ),
        label="Initial Draft",
    )

    assert inspection.sample_n == 2
    assert set(inspection.topics) == {"/doom_image", "/joy"}
    assert draft.source_asset_id == asset.id
    assert draft.status == "draft"
    assert draft.current_revision is not None
    assert draft.current_revision.label == "Initial Draft"
    assert draft.current_revision.revision_number == 1
    assert draft.current_revision.inspection_request_json == {
        "topics": ["/doom_image", "/joy"],
        "sample_n": 2,
        "max_depth": 4,
        "max_sequence_items": 4,
        "on_failure": "warn",
        "topic_type_hints": {},
    }
    assert draft.current_revision.draft_request_json["selected_topics"] == [
        "/doom_image",
        "/joy",
    ]
    assert draft.current_revision.draft_result_json["trigger_topic"] == "/doom_image"
    assert set(draft.current_revision.document.spec.features) == {"image", "buttons"}
    assert draft.current_revision.preview_json is None
    assert draft.confirmed_revision is None


def test_workspace_inspect_asset_normalizes_reader_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    tmp_mcap_file: Path,
) -> None:
    workspace = Workspace.init(tmp_path)
    asset = workspace.register_asset(tmp_mcap_file)
    monkeypatch.setattr(
        "hephaes.workspace.drafts.RosReader.open",
        lambda bag_path, ros_version=None, registry=None: FakeWorkspaceAuthoringReader(
            bag_path=bag_path,
            fail_on_read=True,
        ),
    )

    with pytest.raises(AssetReadError):
        workspace.inspect_asset(asset.id)


def test_workspace_authoring_update_preview_confirm_and_discard_draft(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    tmp_mcap_file: Path,
) -> None:
    workspace = Workspace.init(tmp_path)
    asset = workspace.register_asset(tmp_mcap_file)
    monkeypatch.setattr(
        "hephaes.workspace.drafts.RosReader.open",
        lambda bag_path, ros_version=None, registry=None: FakeWorkspaceAuthoringReader(
            bag_path=bag_path,
        ),
    )

    draft = workspace.create_conversion_draft(
        asset.id,
        inspection_request={"sample_n": 2, "topics": ["/doom_image", "/joy"]},
        draft_request={
            "trigger_topic": "/doom_image",
            "selected_topics": ["/doom_image", "/joy"],
            "max_features_per_topic": 1,
            "label_feature": "buttons",
            "include_preview": False,
        },
    )

    with pytest.raises(ConversionDraftConfirmationError):
        workspace.confirm_conversion_draft(draft.id)

    assert draft.current_revision is not None
    edited_document = draft.current_revision.document.model_copy(
        update={"metadata": {"stage": "edited"}}
    )
    updated = workspace.update_conversion_draft(
        draft.id,
        spec_document=edited_document,
        label="Edited Draft",
    )

    assert updated.status == "draft"
    assert updated.current_revision is not None
    assert updated.current_revision.revision_number == 2
    assert updated.current_revision.label == "Edited Draft"
    assert updated.current_revision.metadata == {"stage": "edited"}
    assert updated.current_revision.preview_json is None
    assert updated.confirmed_revision is None

    previewed = workspace.preview_conversion_draft(draft.id, sample_n=1)

    assert previewed.current_revision is not None
    assert previewed.current_revision.preview_request_json == {
        "sample_n": 1,
        "topic_type_hints": {
            "/doom_image": "custom_msgs/msg/RawImageBGRA",
            "/joy": "sensor_msgs/msg/Joy",
        },
    }
    assert previewed.current_revision.preview_json is not None
    assert len(previewed.current_revision.preview_json["rows"]) == 1

    confirmed = workspace.confirm_conversion_draft(draft.id)

    assert confirmed.status == "confirmed"
    assert confirmed.current_revision is not None
    assert confirmed.confirmed_revision is not None
    assert confirmed.confirmed_revision.id == confirmed.current_revision.id

    revised_document = confirmed.current_revision.document.model_copy(
        update={"metadata": {"stage": "revised"}}
    )
    reopened = workspace.update_conversion_draft(
        draft.id,
        spec_document=revised_document,
        label="Revised Draft",
    )

    assert reopened.status == "draft"
    assert reopened.current_revision is not None
    assert reopened.current_revision.revision_number == 3
    assert reopened.confirmed_revision is None

    discarded = workspace.discard_conversion_draft(draft.id)

    assert discarded.status == "discarded"
    assert discarded.discarded_at is not None

    with pytest.raises(ConversionDraftStateError):
        workspace.update_conversion_draft(
            draft.id,
            spec_document=revised_document,
        )


def test_migrate_workspace_schema_creates_draft_heads_for_legacy_draft_revisions(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.executescript(
            """
            PRAGMA foreign_keys=ON;

            CREATE TABLE workspace_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE assets (
                id TEXT PRIMARY KEY
            );

            CREATE TABLE conversion_configs (
                id TEXT PRIMARY KEY
            );

            CREATE TABLE conversion_draft_revisions (
                id TEXT PRIMARY KEY,
                revision_number INTEGER NOT NULL DEFAULT 1,
                label TEXT NULL,
                saved_config_id TEXT NULL,
                source_asset_id TEXT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                inspection_request_json TEXT NOT NULL DEFAULT '{}',
                inspection_json TEXT NOT NULL DEFAULT '{}',
                draft_request_json TEXT NOT NULL DEFAULT '{}',
                draft_result_json TEXT NOT NULL DEFAULT '{}',
                preview_json TEXT NULL,
                spec_document_path TEXT NOT NULL,
                spec_document_version INTEGER NOT NULL,
                invalid_reason TEXT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO workspace_meta(key, value) VALUES ('schema_version', '9')"
        )
        connection.execute("INSERT INTO assets(id) VALUES ('asset-1')")
        connection.execute("INSERT INTO conversion_configs(id) VALUES ('config-1')")
        connection.execute(
            """
            INSERT INTO conversion_draft_revisions(
                id,
                revision_number,
                label,
                saved_config_id,
                source_asset_id,
                status,
                metadata_json,
                inspection_request_json,
                inspection_json,
                draft_request_json,
                draft_result_json,
                preview_json,
                spec_document_path,
                spec_document_version,
                invalid_reason,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "revision-1",
                1,
                "Legacy Draft",
                "config-1",
                "asset-1",
                "saved",
                "{}",
                "{}",
                "{}",
                "{}",
                "{}",
                '{"rows":[],"checked_records":0,"bad_records":0}',
                "drafts/revision-1.json",
                2,
                None,
                "2026-03-28T10:00:00+00:00",
                "2026-03-28T10:05:00+00:00",
            ),
        )

        migrate_workspace_schema(connection, 9)

        meta = connection.execute(
            "SELECT value FROM workspace_meta WHERE key = 'schema_version'"
        ).fetchone()
        revision_row = connection.execute(
            "SELECT * FROM conversion_draft_revisions WHERE id = 'revision-1'"
        ).fetchone()
        draft_row = connection.execute(
            "SELECT * FROM conversion_drafts WHERE id = 'revision-1'"
        ).fetchone()
    finally:
        connection.close()

    assert meta is not None
    assert meta["value"] == str(WORKSPACE_SCHEMA_VERSION)
    assert revision_row is not None
    assert revision_row["draft_id"] == "revision-1"
    assert revision_row["preview_request_json"] == "{}"
    assert draft_row is not None
    assert draft_row["status"] == "saved"
    assert draft_row["source_asset_id"] == "asset-1"
    assert draft_row["saved_config_id"] == "config-1"
    assert draft_row["current_revision_id"] == "revision-1"
    assert draft_row["confirmed_revision_id"] == "revision-1"


def test_register_and_list_output_artifacts(tmp_path: Path) -> None:
    workspace = Workspace.init(tmp_path)
    outputs_dir = tmp_path / "emitted"
    outputs_dir.mkdir()
    dataset_path = outputs_dir / "episode_0001.parquet"
    dataset_path.write_bytes(b"parquet")
    manifest_path = outputs_dir / "episode_0001.manifest.json"
    manifest_path.write_text('{"episode_id":"episode_0001"}', encoding="utf-8")
    report_path = outputs_dir / "episode_0001.report.md"
    report_path.write_text("# report", encoding="utf-8")

    registered = workspace.register_output_artifacts(
        output_root=outputs_dir,
        source_asset_path="/tmp/source.mcap",
    )
    outputs = workspace.list_output_artifacts()

    assert len(registered) == 3
    assert len(outputs) == 3
    dataset = next(output for output in outputs if output.role == "dataset")
    assert dataset.format == "parquet"
    assert dataset.source_asset_path == "/tmp/source.mcap"
    assert dataset.manifest_available is True
    assert dataset.report_available is True


def test_register_output_artifacts_can_limit_to_specific_paths(tmp_path: Path) -> None:
    workspace = Workspace.init(tmp_path)
    outputs_dir = tmp_path / "emitted"
    outputs_dir.mkdir()
    dataset_path = outputs_dir / "episode_0001.parquet"
    dataset_path.write_bytes(b"parquet")
    manifest_path = outputs_dir / "episode_0001.manifest.json"
    manifest_path.write_text('{"episode_id":"episode_0001"}', encoding="utf-8")
    unrelated_path = outputs_dir / "notes.json"
    unrelated_path.write_text('{"note":"ignore"}', encoding="utf-8")

    registered = workspace.register_output_artifacts(
        output_root=outputs_dir,
        paths=[dataset_path, manifest_path],
        source_asset_path="/tmp/source.mcap",
    )

    assert len(registered) == 2
    assert all(output.output_path != str(unrelated_path.resolve()) for output in registered)


def test_register_output_artifacts_marks_missing_files_on_refresh(
    tmp_path: Path,
    tmp_mcap_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = Workspace.init(tmp_path)
    asset = workspace.register_asset(tmp_mcap_file)
    spec = ConversionSpec(
        schema=SchemaSpec(name="demo", version=1),
        output=OutputSpec(format="parquet"),
    )
    saved_config = workspace.save_conversion_config(
        name="Demo Config",
        spec_document=build_conversion_spec_document(spec),
    )

    class FakeConverter:
        def __init__(self, _file_paths, _mapping, output_dir, **kwargs) -> None:
            self.output_dir = Path(output_dir)

        def convert(self) -> list[Path]:
            dataset_path = self.output_dir / "episode_0001.parquet"
            dataset_path.parent.mkdir(parents=True, exist_ok=True)
            dataset_path.write_bytes(b"parquet")
            dataset_path.with_suffix(".manifest.json").write_text(
                '{"episode_id":"episode_0001"}',
                encoding="utf-8",
            )
            return [dataset_path]

    monkeypatch.setattr("hephaes.workspace.Converter", FakeConverter)

    registered = workspace.run_conversion(asset.id, saved_config_selector=saved_config.id)
    dataset = next(output for output in registered if output.role == "dataset")
    run = workspace.list_conversion_runs()[0]

    Path(dataset.output_path).unlink()

    workspace.register_output_artifacts(
        output_root=run.output_dir,
        conversion_run_id=run.id,
        source_asset_id=asset.id,
        source_asset_path=str(tmp_mcap_file.resolve()),
        saved_config_id=saved_config.id,
    )

    refreshed_dataset = workspace.get_output_artifact_or_raise(dataset.id)
    assert refreshed_dataset.availability_status == "missing"
    assert refreshed_dataset.size_bytes == 0


def test_run_conversion_registers_emitted_outputs(
    tmp_path: Path,
    tmp_mcap_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = Workspace.init(tmp_path)
    asset = workspace.register_asset(tmp_mcap_file)
    spec = ConversionSpec(
        schema=SchemaSpec(name="demo", version=1),
        output=OutputSpec(format="parquet"),
    )
    saved_config = workspace.save_conversion_config(
        name="Demo Config",
        spec_document=build_conversion_spec_document(spec),
    )

    class FakeConverter:
        def __init__(
            self,
            file_paths,
            mapping,
            output_dir,
            *,
            spec,
            max_workers=1,
            **kwargs,
        ) -> None:
            assert len(file_paths) == 1
            assert Path(file_paths[0]).is_file()
            assert Path(file_paths[0]).name == tmp_mcap_file.name
            assert str(tmp_path / ".hephaes" / "imports") in file_paths[0]
            assert mapping is None
            assert spec.schema.name == "demo"
            assert max_workers == 1
            self.output_dir = Path(output_dir)

        def convert(self) -> list[Path]:
            dataset_path = self.output_dir / "episode_0001.parquet"
            dataset_path.parent.mkdir(parents=True, exist_ok=True)
            dataset_path.write_bytes(b"parquet")
            dataset_path.with_suffix(".manifest.json").write_text(
                '{"episode_id":"episode_0001"}',
                encoding="utf-8",
            )
            return [dataset_path]

    monkeypatch.setattr("hephaes.workspace.Converter", FakeConverter)

    outputs = workspace.run_conversion(asset.id, saved_config_selector=saved_config.id)
    jobs = workspace.list_jobs()
    runs = workspace.list_conversion_runs()

    assert len(outputs) == 2
    dataset_output = next(output for output in outputs if output.role == "dataset")
    manifest_output = next(output for output in outputs if output.role == "manifest")
    assert dataset_output.source_asset_id == asset.id
    assert dataset_output.saved_config_id == saved_config.id
    assert dataset_output.source_asset_path == str(tmp_mcap_file.resolve())
    assert dataset_output.manifest_available is True
    assert manifest_output.saved_config_id == saved_config.id
    assert len(jobs) == 1
    assert jobs[0].kind == "conversion"
    assert jobs[0].status == "succeeded"
    assert len(runs) == 1
    assert runs[0].status == "succeeded"
    assert runs[0].job_id == jobs[0].id
    assert runs[0].saved_config_id == saved_config.id
    assert dataset_output.conversion_run_id == runs[0].id
    assert manifest_output.conversion_run_id == runs[0].id


def test_run_conversion_failure_records_job_and_run(
    tmp_path: Path,
    tmp_mcap_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = Workspace.init(tmp_path)
    asset = workspace.register_asset(tmp_mcap_file)
    spec = ConversionSpec(
        schema=SchemaSpec(name="demo", version=1),
        output=OutputSpec(format="parquet"),
    )
    saved_config = workspace.save_conversion_config(
        name="Demo Config",
        spec_document=build_conversion_spec_document(spec),
    )

    class FailingConverter:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def convert(self) -> list[Path]:
            raise RuntimeError("convert boom")

    monkeypatch.setattr("hephaes.workspace.Converter", FailingConverter)

    with pytest.raises(RuntimeError, match="convert boom"):
        workspace.run_conversion(asset.id, saved_config_selector=saved_config.id)

    jobs = workspace.list_jobs()
    runs = workspace.list_conversion_runs()

    assert len(jobs) == 1
    assert jobs[0].status == "failed"
    assert jobs[0].error_message == "convert boom"
    assert len(runs) == 1
    assert runs[0].status == "failed"
    assert runs[0].error_message == "convert boom"
    assert runs[0].job_id == jobs[0].id


def test_get_output_artifact_returns_metadata(tmp_path: Path) -> None:
    workspace = Workspace.init(tmp_path)
    dataset_path = tmp_path / "episode_0001.tfrecord"
    dataset_path.write_bytes(b"tfrecord")
    manifest_path = tmp_path / "episode_0001.manifest.json"
    manifest_path.write_text('{"episode_id":"episode_0001","dataset":{"format":"tfrecord"}}', encoding="utf-8")

    registered = workspace.register_output_artifacts(
        output_root=dataset_path,
        source_asset_id="asset-123",
        saved_config_id="config-123",
    )
    artifact = workspace.get_output_artifact_or_raise(registered[0].id)

    assert artifact.source_asset_id == "asset-123"
    assert artifact.saved_config_id == "config-123"
    assert artifact.output_path == str(dataset_path.resolve())
    assert artifact.manifest_available is True
    assert artifact.metadata["manifest"]["dataset"]["format"] == "tfrecord"
