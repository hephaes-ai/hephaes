from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from scripts.build_sidecar import build_pyinstaller_command


def test_build_pyinstaller_command_collects_required_rosbags_modules(tmp_path: Path):
    backend_dir = tmp_path / "backend"
    hephaes_src_dir = tmp_path / "hephaes-src"
    dist_dir = tmp_path / "dist"
    build_dir = tmp_path / "build"
    spec_dir = tmp_path / "spec"
    args = Namespace(mode="onefile", name="hephaes-backend-sidecar")

    command = build_pyinstaller_command(
        args=args,
        backend_dir=backend_dir,
        hephaes_src_dir=hephaes_src_dir,
        dist_dir=dist_dir,
        build_dir=build_dir,
        spec_dir=spec_dir,
    )

    collected_modules = [
        command[index + 1]
        for index, value in enumerate(command)
        if value == "--collect-submodules"
    ]

    assert "rosbags.serde" in collected_modules
    assert "rosbags.typesys.stores" in collected_modules
    assert str(backend_dir / "app" / "desktop_main.py") == command[-1]
