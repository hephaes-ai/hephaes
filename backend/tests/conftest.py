from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
HEPHAES_SRC_DIR = REPO_ROOT / "hephaes" / "src"

for import_path in (BACKEND_DIR, HEPHAES_SRC_DIR):
    resolved_path = str(import_path)
    if resolved_path not in sys.path:
        sys.path.insert(0, resolved_path)


@pytest.fixture()
def backend_outputs_dir(tmp_path: Path) -> Path:
    return tmp_path / "outputs"


@pytest.fixture()
def backend_raw_data_dir(tmp_path: Path) -> Path:
    return tmp_path / "raw"


@pytest.fixture()
def sample_asset_file(tmp_path: Path) -> Path:
    asset_path = tmp_path / "sample_asset.mcap"
    asset_path.write_bytes(b"hephaes-backend-test\n")
    return asset_path


@pytest.fixture()
def client(
    monkeypatch: pytest.MonkeyPatch,
    backend_outputs_dir: Path,
    backend_raw_data_dir: Path,
    tmp_path: Path,
):
    monkeypatch.setenv("HEPHAES_BACKEND_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HEPHAES_BACKEND_DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("HEPHAES_BACKEND_OUTPUTS_DIR", str(backend_outputs_dir))
    monkeypatch.setenv("HEPHAES_BACKEND_RAW_DATA_DIR", str(backend_raw_data_dir))
    monkeypatch.setenv("HEPHAES_BACKEND_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("HEPHAES_WORKSPACE_ROOT", str(tmp_path / "workspace"))

    import app.config as app_config
    from app.config import get_settings

    monkeypatch.setattr(app_config, "DEFAULT_JOB_EXECUTION_MODE", "inline")
    monkeypatch.setattr(app_config, "DEFAULT_JOB_MAX_WORKERS", 1)

    get_settings.cache_clear()

    from hephaes import Workspace
    from app.main import create_app

    Workspace.init(tmp_path / "workspace", exist_ok=True)
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()


@pytest.fixture()
def empty_registry_client(
    monkeypatch: pytest.MonkeyPatch,
    backend_outputs_dir: Path,
    backend_raw_data_dir: Path,
    tmp_path: Path,
):
    monkeypatch.setenv("HEPHAES_BACKEND_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HEPHAES_BACKEND_DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("HEPHAES_BACKEND_OUTPUTS_DIR", str(backend_outputs_dir))
    monkeypatch.setenv("HEPHAES_BACKEND_RAW_DATA_DIR", str(backend_raw_data_dir))
    monkeypatch.setenv("HEPHAES_BACKEND_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("HEPHAES_WORKSPACE_ROOT", str(tmp_path / "workspace"))

    import app.config as app_config
    from app.config import get_settings
    from app.main import create_app

    monkeypatch.setattr(app_config, "DEFAULT_JOB_EXECUTION_MODE", "inline")
    monkeypatch.setattr(app_config, "DEFAULT_JOB_MAX_WORKERS", 1)

    get_settings.cache_clear()

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()
