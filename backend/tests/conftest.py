from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def backend_db_path(tmp_path: Path) -> Path:
    return tmp_path / "backend_test.db"


@pytest.fixture()
def sample_asset_file(tmp_path: Path) -> Path:
    asset_path = tmp_path / "sample_asset.mcap"
    asset_path.write_bytes(b"hephaes-backend-test\n")
    return asset_path


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, backend_db_path: Path):
    monkeypatch.setenv("HEPHAES_BACKEND_DB_PATH", str(backend_db_path))

    from backend.app.config import get_settings

    get_settings.cache_clear()

    from backend.app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()
