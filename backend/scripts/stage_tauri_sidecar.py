"""Build and stage the backend sidecar where Tauri expects it."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and stage the Hephaes backend sidecar for Tauri.",
    )
    parser.add_argument(
        "--target-triple",
        default=None,
        help="Rust target triple suffix to stage the sidecar under.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to place the staged sidecar binary in.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean previous PyInstaller artifacts before building.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even if the staged sidecar already looks current.",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def resolve_paths() -> tuple[Path, Path]:
    script_path = Path(__file__).resolve()
    backend_dir = script_path.parents[1]
    frontend_tauri_dir = backend_dir.parent / "frontend" / "src-tauri"
    return backend_dir, frontend_tauri_dir


def collect_source_paths(backend_dir: Path) -> list[Path]:
    source_paths = [
        backend_dir / "pyproject.toml",
        backend_dir / "app",
        backend_dir / "scripts" / "build_sidecar.py",
        backend_dir / "scripts" / "stage_tauri_sidecar.py",
        backend_dir.parent / "hephaes" / "pyproject.toml",
        backend_dir.parent / "hephaes" / "src",
    ]
    return [path for path in source_paths if path.exists()]


def newest_mtime(path: Path) -> float:
    if path.is_file():
        return path.stat().st_mtime

    latest_mtime = path.stat().st_mtime
    for child in path.rglob("*"):
        if child.is_file():
            latest_mtime = max(latest_mtime, child.stat().st_mtime)
    return latest_mtime


def resolve_target_triple() -> str:
    completed = subprocess.run(
        ["rustc", "-vV"],
        check=True,
        capture_output=True,
        text=True,
    )
    for line in completed.stdout.splitlines():
        if line.startswith("host: "):
            return line.removeprefix("host: ").strip()
    raise RuntimeError("could not determine rust host target triple from `rustc -vV`")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    backend_dir, frontend_tauri_dir = resolve_paths()
    target_triple = args.target_triple or resolve_target_triple()
    output_dir = Path(args.output_dir) if args.output_dir else frontend_tauri_dir / "binaries"
    staged_name = f"hephaes-backend-sidecar-{target_triple}"

    if target_triple.endswith("windows-msvc") or target_triple.endswith("windows-gnu"):
        source_name = "hephaes-backend-sidecar.exe"
        staged_name = f"{staged_name}.exe"
    else:
        source_name = "hephaes-backend-sidecar"

    output_dir.mkdir(parents=True, exist_ok=True)
    staged_binary_path = output_dir / staged_name

    needs_rebuild = args.force or not staged_binary_path.exists()
    if not needs_rebuild:
        staged_mtime = staged_binary_path.stat().st_mtime
        source_paths = collect_source_paths(backend_dir)
        needs_rebuild = any(newest_mtime(path) > staged_mtime for path in source_paths)

    if needs_rebuild:
        build_command = [
            sys.executable,
            str(backend_dir / "scripts" / "build_sidecar.py"),
            "--mode",
            "onefile",
        ]
        if args.clean:
            build_command.append("--clean")

        subprocess.run(build_command, check=True, cwd=str(backend_dir))

        built_binary_path = backend_dir / "dist" / source_name
        if not built_binary_path.exists():
            raise FileNotFoundError(f"expected built sidecar at {built_binary_path}")

        shutil.copy2(built_binary_path, staged_binary_path)

    current_mode = staged_binary_path.stat().st_mode
    staged_binary_path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(staged_binary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
