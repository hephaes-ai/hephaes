from __future__ import annotations

from pathlib import Path

import hephaes
from hephaes.cli import main
from hephaes.models import BagMetadata, Topic


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
