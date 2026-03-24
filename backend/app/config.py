"""Local configuration for the FastAPI backend."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

DEFAULT_RERUN_SDK_VERSION = "0.22"
DEFAULT_RERUN_RECORDING_FORMAT_VERSION = "1"
DEFAULT_JOB_EXECUTION_MODE = "background"
DEFAULT_JOB_MAX_WORKERS = 4


def _as_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_rerun_sdk_version() -> str:
    configured_version = os.environ.get("HEPHAES_RERUN_SDK_VERSION")
    if configured_version and configured_version.strip():
        return configured_version.strip()

    try:
        return version("rerun-sdk")
    except PackageNotFoundError:
        return DEFAULT_RERUN_SDK_VERSION


@dataclass(frozen=True)
class Settings:
    app_name: str
    debug: bool
    repo_root: Path
    backend_dir: Path
    data_dir: Path
    raw_data_dir: Path
    outputs_dir: Path
    database_path: Path
    database_url: str
    job_execution_mode: str
    job_max_workers: int
    rerun_sdk_version: str
    rerun_recording_format_version: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    data_dir = Path(os.environ.get("HEPHAES_BACKEND_DATA_DIR", backend_dir / "data")).expanduser()
    raw_data_dir = Path(
        os.environ.get("HEPHAES_BACKEND_RAW_DATA_DIR", data_dir / "raw"),
    ).expanduser()
    outputs_dir = Path(
        os.environ.get("HEPHAES_BACKEND_OUTPUTS_DIR", data_dir / "outputs"),
    ).expanduser()
    database_path = Path(
        os.environ.get("HEPHAES_BACKEND_DB_PATH", data_dir / "app.db"),
    ).expanduser()

    return Settings(
        app_name=os.environ.get("HEPHAES_BACKEND_APP_NAME", "Hephaes Backend"),
        debug=_as_bool(os.environ.get("HEPHAES_BACKEND_DEBUG")),
        repo_root=repo_root,
        backend_dir=backend_dir,
        data_dir=data_dir,
        raw_data_dir=raw_data_dir,
        outputs_dir=outputs_dir,
        database_path=database_path,
        database_url=f"sqlite:///{database_path}",
        job_execution_mode=DEFAULT_JOB_EXECUTION_MODE,
        job_max_workers=DEFAULT_JOB_MAX_WORKERS,
        rerun_sdk_version=_resolve_rerun_sdk_version(),
        rerun_recording_format_version=os.environ.get(
            "HEPHAES_RERUN_RECORDING_FORMAT_VERSION",
            DEFAULT_RERUN_RECORDING_FORMAT_VERSION,
        ).strip(),
    )
