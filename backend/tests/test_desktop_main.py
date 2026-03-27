from __future__ import annotations

from app.desktop_main import parse_args


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
