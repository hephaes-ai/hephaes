from __future__ import annotations

from app.config import get_settings
from app.desktop_main import build_log_config, parse_args


def test_parse_args_uses_env_defaults(monkeypatch):
    monkeypatch.setenv("HEPHAES_BACKEND_HOST", "127.0.0.1")
    monkeypatch.setenv("HEPHAES_BACKEND_PORT", "8123")
    monkeypatch.setenv("HEPHAES_BACKEND_LOG_LEVEL", "warning")

    args = parse_args([])

    assert args.host == "127.0.0.1"
    assert args.port == 8123
    assert args.log_level == "warning"


def test_parse_args_prefers_explicit_cli_values(monkeypatch):
    monkeypatch.setenv("HEPHAES_BACKEND_HOST", "127.0.0.1")
    monkeypatch.setenv("HEPHAES_BACKEND_PORT", "8123")
    monkeypatch.setenv("HEPHAES_BACKEND_LOG_LEVEL", "warning")

    args = parse_args(["--host", "0.0.0.0", "--port", "9000", "--log-level", "debug"])

    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.log_level == "debug"


def test_build_log_config_writes_backend_logs_to_configured_directory(
    monkeypatch,
    tmp_path,
):
    log_dir = tmp_path / "logs"
    monkeypatch.setenv("HEPHAES_BACKEND_LOG_DIR", str(log_dir))
    get_settings.cache_clear()

    log_config = build_log_config("warning")

    assert log_dir.is_dir()
    assert log_config["handlers"]["file"]["filename"] == str(log_dir / "backend.log")
    assert log_config["handlers"]["access_file"]["filename"] == str(
        log_dir / "backend-access.log"
    )
    assert log_config["root"]["level"] == "WARNING"

    get_settings.cache_clear()
