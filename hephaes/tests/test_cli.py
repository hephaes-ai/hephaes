from __future__ import annotations

from pathlib import Path

import hephaes
from hephaes.cli import main


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
