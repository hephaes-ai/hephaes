from __future__ import annotations

from pathlib import Path

import hephaes
from hephaes.conversion.spec_io import build_conversion_spec_document, dump_conversion_spec_document
from hephaes.cli import main
from hephaes.conversion.introspection import InspectionResult, TopicInspectionResult
from hephaes.models import BagMetadata, ConversionSpec, OutputSpec, SchemaSpec, Topic


def test_cli_version(capsys) -> None:
    exit_code = main(["--version"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == f"hephaes {hephaes.__version__}"


def test_cli_init_creates_workspace(tmp_path: Path, capsys) -> None:
    workspace_root = tmp_path / "demo"

    exit_code = main(["init", str(workspace_root)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Initialized Hephaes workspace" in captured.out
    assert (workspace_root / ".hephaes" / "workspace.sqlite3").is_file()


def test_cli_add_registers_assets_in_workspace(
    tmp_path: Path,
    tmp_mcap_file: Path,
    capsys,
) -> None:
    main(["init", str(tmp_path)])
    capsys.readouterr()

    exit_code = main(["add", "--workspace", str(tmp_path), str(tmp_mcap_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert str(tmp_mcap_file.resolve()) in captured.out
    assert "\tmcap\t" in captured.out


def test_cli_ls_assets_lists_registered_assets(
    tmp_path: Path,
    tmp_bag_file: Path,
    capsys,
) -> None:
    main(["init", str(tmp_path)])
    main(["add", "--workspace", str(tmp_path), str(tmp_bag_file)])
    capsys.readouterr()

    exit_code = main(["ls", "assets", "--workspace", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert str(tmp_bag_file.resolve()) in captured.out
    assert "\tpending\tbag\t" in captured.out


def test_cli_duplicate_add_returns_nonzero(
    tmp_path: Path,
    tmp_bag_file: Path,
    capsys,
) -> None:
    main(["init", str(tmp_path)])
    main(["add", "--workspace", str(tmp_path), str(tmp_bag_file)])
    capsys.readouterr()

    exit_code = main(["add", "--workspace", str(tmp_path), str(tmp_bag_file)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "already registered" in captured.err


def test_cli_requires_workspace_for_add(tmp_path: Path, tmp_bag_file: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["add", str(tmp_bag_file)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "no hephaes workspace found" in captured.err


def test_cli_index_by_asset_id(
    tmp_path: Path,
    tmp_mcap_file: Path,
    capsys,
    monkeypatch,
) -> None:
    main(["init", str(tmp_path)])
    capsys.readouterr()
    main(["add", "--workspace", str(tmp_path), str(tmp_mcap_file)])
    add_output = capsys.readouterr().out.strip()
    asset_id = add_output.split("\t", 1)[0]

    def fake_profile_asset_file(file_path: str, *, max_workers: int = 1) -> BagMetadata:
        assert file_path == str(tmp_mcap_file.resolve())
        assert max_workers == 1
        return BagMetadata(
            path=file_path,
            file_path=file_path,
            ros_version="ROS2",
            storage_format="mcap",
            file_size_bytes=100,
            start_timestamp=1_000_000_000,
            end_timestamp=2_000_000_000,
            start_time_iso="1970-01-01T00:00:01+00:00",
            end_time_iso="1970-01-01T00:00:02+00:00",
            duration_seconds=1.0,
            message_count=12,
            topics=[
                Topic(
                    name="/camera/image",
                    message_type="sensor_msgs/Image",
                    message_count=12,
                    rate_hz=12.0,
                )
            ],
            compression_format="none",
        )

    monkeypatch.setattr("hephaes.workspace.profile_asset_file", fake_profile_asset_file)

    exit_code = main(["index", "--workspace", str(tmp_path), asset_id])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"status": "indexed"' in captured.out
    assert '"message_count": 12' in captured.out
    assert '"sensor_types": ["camera"]' in captured.out


def test_cli_index_by_file_path(
    tmp_path: Path,
    tmp_bag_file: Path,
    capsys,
    monkeypatch,
) -> None:
    main(["init", str(tmp_path)])
    main(["add", "--workspace", str(tmp_path), str(tmp_bag_file)])
    capsys.readouterr()

    def fake_profile_asset_file(file_path: str, *, max_workers: int = 1) -> BagMetadata:
        return BagMetadata(
            path=file_path,
            file_path=file_path,
            ros_version="ROS1",
            storage_format="bag",
            file_size_bytes=10,
            start_timestamp=None,
            end_timestamp=None,
            start_time_iso=None,
            end_time_iso=None,
            duration_seconds=0.0,
            message_count=0,
            topics=[],
            compression_format="none",
        )

    monkeypatch.setattr("hephaes.workspace.profile_asset_file", fake_profile_asset_file)

    exit_code = main(["index", "--workspace", str(tmp_path), str(tmp_bag_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"file_path": "' in captured.out
    assert str(tmp_bag_file.resolve()) in captured.out


def test_cli_index_requires_selector_or_all(tmp_path: Path, capsys) -> None:
    main(["init", str(tmp_path)])
    capsys.readouterr()

    exit_code = main(["index", "--workspace", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "provide one or more asset selectors or use --all" in captured.err


def test_cli_inspect_direct_path(
    tmp_path: Path,
    tmp_mcap_file: Path,
    capsys,
    monkeypatch,
) -> None:
    def fake_inspect_bag(
        bag_path: str,
        *,
        topics=None,
        sample_n: int = 8,
        max_depth: int = 4,
        max_sequence_items: int = 4,
        on_failure: str = "warn",
        topic_type_hints=None,
    ) -> InspectionResult:
        assert bag_path == str(tmp_mcap_file.resolve())
        assert topics == ["/camera"]
        assert sample_n == 2
        assert max_depth == 3
        assert max_sequence_items == 2
        assert on_failure == "fail"
        return InspectionResult(
            bag_path=bag_path,
            ros_version="ROS2",
            sample_n=sample_n,
            topics={
                "/camera": TopicInspectionResult(
                    topic="/camera",
                    message_type="sensor_msgs/Image",
                    sampled_message_count=1,
                )
            },
        )

    monkeypatch.setattr("hephaes.cli.inspect_bag", fake_inspect_bag)

    exit_code = main(
        [
            "inspect",
            str(tmp_mcap_file),
            "--topic",
            "/camera",
            "--sample-n",
            "2",
            "--max-depth",
            "3",
            "--max-sequence-items",
            "2",
            "--on-failure",
            "fail",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"bag_path": "' in captured.out
    assert '"ros_version": "ROS2"' in captured.out
    assert '"/camera"' in captured.out


def test_cli_inspect_registered_asset_by_id(
    tmp_path: Path,
    tmp_bag_file: Path,
    capsys,
    monkeypatch,
) -> None:
    main(["init", str(tmp_path)])
    capsys.readouterr()
    main(["add", "--workspace", str(tmp_path), str(tmp_bag_file)])
    add_output = capsys.readouterr().out.strip()
    asset_id = add_output.split("\t", 1)[0]

    def fake_inspect_bag(
        bag_path: str,
        *,
        topics=None,
        sample_n: int = 8,
        max_depth: int = 4,
        max_sequence_items: int = 4,
        on_failure: str = "warn",
        topic_type_hints=None,
    ) -> InspectionResult:
        assert bag_path == str(tmp_bag_file.resolve())
        return InspectionResult(
            bag_path=bag_path,
            ros_version="ROS1",
            sample_n=sample_n,
            topics={
                "/joy": TopicInspectionResult(
                    topic="/joy",
                    message_type="sensor_msgs/Joy",
                    sampled_message_count=1,
                )
            },
        )

    monkeypatch.setattr("hephaes.cli.inspect_bag", fake_inspect_bag)

    exit_code = main(["inspect", "--workspace", str(tmp_path), asset_id])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"ros_version": "ROS1"' in captured.out
    assert str(tmp_bag_file.resolve()) in captured.out


def test_cli_configs_save_and_ls(tmp_path: Path, capsys) -> None:
    main(["init", str(tmp_path)])
    capsys.readouterr()

    spec = ConversionSpec(
        schema=SchemaSpec(name="saved_demo", version=1),
        output=OutputSpec(format="parquet"),
    )
    document_path = tmp_path / "saved-spec.json"
    document_path.write_text(
        dump_conversion_spec_document(build_conversion_spec_document(spec), format="json"),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "configs",
            "save",
            "--workspace",
            str(tmp_path),
            "Saved Demo",
            str(document_path),
            "--description",
            "demo config",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "\tSaved Demo\t" in captured.out


def test_cli_outputs_ls_and_show(tmp_path: Path, capsys) -> None:
    main(["init", str(tmp_path)])
    capsys.readouterr()

    workspace_outputs = tmp_path / "outputs"
    workspace_outputs.mkdir()
    dataset_path = workspace_outputs / "episode_0001.parquet"
    dataset_path.write_bytes(b"parquet")
    manifest_path = workspace_outputs / "episode_0001.manifest.json"
    manifest_path.write_text('{"episode_id":"episode_0001"}', encoding="utf-8")

    from hephaes import Workspace

    workspace = Workspace.open(tmp_path)
    registered = workspace.register_output_artifacts(
        output_root=workspace_outputs,
        source_asset_path="/tmp/source.mcap",
    )

    exit_code = main(["outputs", "ls", "--workspace", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert str(dataset_path.resolve()) in captured.out
    assert "\tparquet\tdataset\t" in captured.out

    dataset_id = next(output.id for output in registered if output.role == "dataset")
    exit_code = main(["outputs", "show", "--workspace", str(tmp_path), dataset_id])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"format": "parquet"' in captured.out
    assert '"manifest_available": true' in captured.out


def test_cli_convert_with_saved_config(
    tmp_path: Path,
    tmp_bag_file: Path,
    capsys,
    monkeypatch,
) -> None:
    main(["init", str(tmp_path)])
    capsys.readouterr()
    main(["add", "--workspace", str(tmp_path), str(tmp_bag_file)])
    add_output = capsys.readouterr().out.strip()
    asset_id = add_output.split("\t", 1)[0]

    spec = ConversionSpec(
        schema=SchemaSpec(name="convert_demo", version=1),
        output=OutputSpec(format="parquet"),
    )
    document_path = tmp_path / "convert-spec.json"
    document_path.write_text(
        dump_conversion_spec_document(build_conversion_spec_document(spec), format="json"),
        encoding="utf-8",
    )
    main(["configs", "save", "--workspace", str(tmp_path), "Convert Demo", str(document_path)])
    capsys.readouterr()

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
            assert file_paths == [str(tmp_bag_file.resolve())]
            assert mapping is None
            assert spec.schema.name == "convert_demo"
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

    exit_code = main(
        [
            "convert",
            "--workspace",
            str(tmp_path),
            "--config",
            "Convert Demo",
            asset_id,
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"output_count": 2' in captured.out
    assert '"role": "dataset"' in captured.out
    assert '"role": "manifest"' in captured.out


def test_cli_convert_requires_exactly_one_config_source(
    tmp_path: Path,
    tmp_bag_file: Path,
    capsys,
) -> None:
    main(["init", str(tmp_path)])
    capsys.readouterr()

    exit_code = main(["convert", "--workspace", str(tmp_path), str(tmp_bag_file)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "provide exactly one of --config or --spec-document" in captured.err


def test_cli_convert_with_direct_path_and_spec_document(
    tmp_path: Path,
    tmp_mcap_file: Path,
    capsys,
    monkeypatch,
) -> None:
    main(["init", str(tmp_path)])
    capsys.readouterr()

    spec = ConversionSpec(
        schema=SchemaSpec(name="direct_demo", version=1),
        output=OutputSpec(format="parquet"),
    )
    document_path = tmp_path / "direct-spec.json"
    document_path.write_text(
        dump_conversion_spec_document(build_conversion_spec_document(spec), format="json"),
        encoding="utf-8",
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
            assert file_paths == [str(tmp_mcap_file.resolve())]
            assert mapping is None
            assert spec.schema.name == "direct_demo"
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

    exit_code = main(
        [
            "convert",
            "--workspace",
            str(tmp_path),
            "--spec-document",
            str(document_path),
            str(tmp_mcap_file),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"output_count": 2' in captured.out
    assert str(tmp_mcap_file.resolve()) in captured.out
