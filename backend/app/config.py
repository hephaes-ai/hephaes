"""Local configuration for the FastAPI backend."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _as_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
    )
