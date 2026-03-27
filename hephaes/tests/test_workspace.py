from __future__ import annotations

from pathlib import Path

import pytest

from hephaes import (
    AssetAlreadyRegisteredError,
    AssetNotFoundError,
    ConversionConfigAlreadyExistsError,
    InvalidAssetPathError,
    TagAlreadyExistsError,
    Workspace,
    WorkspaceAlreadyExistsError,
    WorkspaceNotFoundError,
)
from hephaes.conversion.spec_io import build_conversion_spec_document, dump_conversion_spec_document
from hephaes.models import BagMetadata, Topic
from hephaes.models import ConversionSpec, OutputSpec, SchemaSpec


def test_workspace_init_creates_layout(tmp_path: Path) -> None:
    workspace = Workspace.init(tmp_path)

    assert workspace.root == tmp_path
    assert (tmp_path / ".hephaes").is_dir()
    assert (tmp_path / ".hephaes" / "workspace.sqlite3").is_file()
    assert (tmp_path / ".hephaes" / "imports").is_dir()
    assert (tmp_path / ".hephaes" / "outputs").is_dir()
    assert (tmp_path / ".hephaes" / "specs").is_dir()
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

    assert len(outputs) == 2
    dataset_output = next(output for output in outputs if output.role == "dataset")
    manifest_output = next(output for output in outputs if output.role == "manifest")
    assert dataset_output.source_asset_id == asset.id
    assert dataset_output.saved_config_id == saved_config.id
    assert dataset_output.source_asset_path == str(tmp_mcap_file.resolve())
    assert dataset_output.manifest_available is True
    assert manifest_output.saved_config_id == saved_config.id


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
