"""Configuration for the local FastAPI backend."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_JOB_EXECUTION_MODE = "background"
DEFAULT_JOB_MAX_WORKERS = 4
DEFAULT_APP_NAME = "Hephaes Backend"
DEFAULT_CORS_ALLOW_ORIGIN_REGEX = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"


def _as_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str
    debug: bool
    desktop_mode: bool
    app_db_path: Path
    data_dir: Path
    workspace_root: Path
    raw_data_dir: Path
    outputs_dir: Path
    log_dir: Path
    cors_allow_origin_regex: str
    job_execution_mode: str
    job_max_workers: int


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


def _resolve_app_db_path(*, data_dir: Path) -> Path:
    configured_app_db_path = os.environ.get("HEPHAES_BACKEND_DB_PATH")
    if configured_app_db_path and configured_app_db_path.strip():
        return Path(configured_app_db_path).expanduser()
    return (data_dir / "app.db").expanduser()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    desktop_mode = _as_bool(os.environ.get("HEPHAES_DESKTOP_MODE"))
    data_dir = _resolve_default_data_dir(desktop_mode=desktop_mode)
    app_db_path = _resolve_app_db_path(data_dir=data_dir)
    workspace_root = _resolve_workspace_root(data_dir=data_dir)
    raw_data_dir = _resolve_path("HEPHAES_BACKEND_RAW_DATA_DIR", data_dir / "raw")
    outputs_dir = _resolve_path("HEPHAES_BACKEND_OUTPUTS_DIR", data_dir / "outputs")
    log_dir = _resolve_path("HEPHAES_BACKEND_LOG_DIR", data_dir / "logs")
    cors_allow_origin_regex = os.environ.get(
        "HEPHAES_BACKEND_CORS_ALLOW_ORIGIN_REGEX",
        DEFAULT_CORS_ALLOW_ORIGIN_REGEX,
    ).strip()

    return Settings(
        app_name=os.environ.get("HEPHAES_BACKEND_APP_NAME", DEFAULT_APP_NAME),
        debug=_as_bool(os.environ.get("HEPHAES_BACKEND_DEBUG")),
        desktop_mode=desktop_mode,
        app_db_path=app_db_path,
        data_dir=data_dir,
        workspace_root=workspace_root,
        raw_data_dir=raw_data_dir,
        outputs_dir=outputs_dir,
        log_dir=log_dir,
        cors_allow_origin_regex=cors_allow_origin_regex,
        job_execution_mode=DEFAULT_JOB_EXECUTION_MODE,
        job_max_workers=DEFAULT_JOB_MAX_WORKERS,
    )
