"""Build a packaged desktop backend executable with PyInstaller."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the Hephaes backend desktop sidecar.",
    )
    parser.add_argument(
        "--mode",
        choices=("onedir", "onefile"),
        default="onedir",
        help="PyInstaller bundle mode.",
    )
    parser.add_argument(
        "--name",
        default="hephaes-backend-sidecar",
        help="Output executable name.",
    )
    parser.add_argument(
        "--dist-dir",
        default=None,
        help="Directory to place build artifacts in.",
    )
    parser.add_argument(
        "--build-dir",
        default=None,
        help="Directory for intermediate PyInstaller artifacts.",
    )
    parser.add_argument(
        "--spec-dir",
        default=None,
        help="Directory to place the generated spec file in.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete prior artifacts before building.",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def resolve_paths() -> tuple[Path, Path, Path]:
    script_path = Path(__file__).resolve()
    backend_dir = script_path.parents[1]
    repo_root = backend_dir.parent
    hephaes_src_dir = repo_root / "hephaes" / "src"
    return backend_dir, repo_root, hephaes_src_dir


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    backend_dir, _repo_root, hephaes_src_dir = resolve_paths()

    dist_dir = Path(args.dist_dir) if args.dist_dir else backend_dir / "dist"
    build_dir = Path(args.build_dir) if args.build_dir else backend_dir / "build"
    spec_dir = Path(args.spec_dir) if args.spec_dir else build_dir / "spec"

    if args.clean:
        for path in (dist_dir, build_dir):
            if path.exists():
                shutil.rmtree(path)

    dist_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    spec_dir.mkdir(parents=True, exist_ok=True)

    entrypoint_path = backend_dir / "app" / "desktop_main.py"
    mode_flag = "--onedir" if args.mode == "onedir" else "--onefile"

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        mode_flag,
        "--name",
        args.name,
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(build_dir),
        "--specpath",
        str(spec_dir),
        "--paths",
        str(backend_dir),
        "--paths",
        str(hephaes_src_dir),
        "--collect-submodules",
        "app",
        "--collect-submodules",
        "hephaes",
        str(entrypoint_path),
    ]

    subprocess.run(command, check=True, cwd=str(backend_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
