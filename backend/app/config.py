"""Configuration for the local FastAPI backend."""

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
DEFAULT_APP_NAME = "Hephaes Backend"
DEFAULT_CORS_ALLOW_ORIGIN_REGEX = r"https?://(localhost|127\.0\.0\.1|app\.rerun\.io)(:\d+)?"


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
    desktop_mode: bool
    data_dir: Path
    workspace_root: Path
    raw_data_dir: Path
    outputs_dir: Path
    log_dir: Path
    database_path: Path
    database_url: str
    cors_allow_origin_regex: str
    job_execution_mode: str
    job_max_workers: int
    rerun_sdk_version: str
    rerun_recording_format_version: str


def _resolve_default_data_dir(*, desktop_mode: bool) -> Path:
    configured_data_dir = os.environ.get("HEPHAES_BACKEND_DATA_DIR")
    if configured_data_dir and configured_data_dir.strip():
        return Path(configured_data_dir).expanduser()

    if desktop_mode:
        return (Path.home() / ".hephaes" / "backend").expanduser()

    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    return backend_dir / "data"


def _resolve_path(setting_name: str, default: Path) -> Path:
    configured_value = os.environ.get(setting_name)
    if configured_value and configured_value.strip():
        return Path(configured_value).expanduser()
    return default.expanduser()


def _resolve_workspace_root(*, data_dir: Path) -> Path:
    configured_workspace_root = os.environ.get("HEPHAES_WORKSPACE_ROOT")
    if configured_workspace_root and configured_workspace_root.strip():
        return Path(configured_workspace_root).expanduser()
    return (data_dir / "workspace").expanduser()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    desktop_mode = _as_bool(os.environ.get("HEPHAES_DESKTOP_MODE"))
    data_dir = _resolve_default_data_dir(desktop_mode=desktop_mode)
    workspace_root = _resolve_workspace_root(data_dir=data_dir)
    raw_data_dir = _resolve_path("HEPHAES_BACKEND_RAW_DATA_DIR", data_dir / "raw")
    outputs_dir = _resolve_path("HEPHAES_BACKEND_OUTPUTS_DIR", data_dir / "outputs")
    log_dir = _resolve_path("HEPHAES_BACKEND_LOG_DIR", data_dir / "logs")
    database_path = _resolve_path("HEPHAES_BACKEND_DB_PATH", data_dir / "app.db")
    cors_allow_origin_regex = os.environ.get(
        "HEPHAES_BACKEND_CORS_ALLOW_ORIGIN_REGEX",
        DEFAULT_CORS_ALLOW_ORIGIN_REGEX,
    ).strip()

    return Settings(
        app_name=os.environ.get("HEPHAES_BACKEND_APP_NAME", DEFAULT_APP_NAME),
        debug=_as_bool(os.environ.get("HEPHAES_BACKEND_DEBUG")),
        desktop_mode=desktop_mode,
        data_dir=data_dir,
        workspace_root=workspace_root,
        raw_data_dir=raw_data_dir,
        outputs_dir=outputs_dir,
        log_dir=log_dir,
        database_path=database_path,
        database_url=f"sqlite:///{database_path}",
        cors_allow_origin_regex=cors_allow_origin_regex,
        job_execution_mode=DEFAULT_JOB_EXECUTION_MODE,
        job_max_workers=DEFAULT_JOB_MAX_WORKERS,
        rerun_sdk_version=_resolve_rerun_sdk_version(),
        rerun_recording_format_version=os.environ.get(
            "HEPHAES_RERUN_RECORDING_FORMAT_VERSION",
            DEFAULT_RERUN_RECORDING_FORMAT_VERSION,
        ).strip(),
    )
