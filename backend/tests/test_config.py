from __future__ import annotations

from pathlib import Path

from app.config import get_settings


def clear_settings_cache() -> None:
    get_settings.cache_clear()


def test_get_settings_uses_desktop_defaults_when_desktop_mode_is_enabled(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HEPHAES_DESKTOP_MODE", "1")
    for setting_name in (
        "HEPHAES_BACKEND_DATA_DIR",
        "HEPHAES_BACKEND_RAW_DATA_DIR",
        "HEPHAES_BACKEND_OUTPUTS_DIR",
        "HEPHAES_BACKEND_LOG_DIR",
        "HEPHAES_BACKEND_CORS_ALLOW_ORIGIN_REGEX",
    ):
        monkeypatch.delenv(setting_name, raising=False)

    clear_settings_cache()
    settings = get_settings()

    expected_data_dir = tmp_path / ".hephaes" / "backend"
    assert settings.desktop_mode is True
    assert settings.data_dir == expected_data_dir
    assert settings.raw_data_dir == expected_data_dir / "raw"
    assert settings.outputs_dir == expected_data_dir / "outputs"
    assert settings.log_dir == expected_data_dir / "logs"

    clear_settings_cache()


def test_get_settings_prefers_explicit_env_paths(monkeypatch, tmp_path: Path):
    data_dir = tmp_path / "data"
    raw_dir = tmp_path / "raw"
    outputs_dir = tmp_path / "outputs"
    log_dir = tmp_path / "logs"
    cors_regex = r"https?://example\.com(:\d+)?"

    monkeypatch.setenv("HEPHAES_BACKEND_DATA_DIR", str(data_dir))
    monkeypatch.setenv("HEPHAES_BACKEND_RAW_DATA_DIR", str(raw_dir))
    monkeypatch.setenv("HEPHAES_BACKEND_OUTPUTS_DIR", str(outputs_dir))
    monkeypatch.setenv("HEPHAES_BACKEND_LOG_DIR", str(log_dir))
    monkeypatch.setenv("HEPHAES_BACKEND_CORS_ALLOW_ORIGIN_REGEX", cors_regex)

    clear_settings_cache()
    settings = get_settings()

    assert settings.data_dir == data_dir
    assert settings.raw_data_dir == raw_dir
    assert settings.outputs_dir == outputs_dir
    assert settings.log_dir == log_dir
    assert settings.cors_allow_origin_regex == cors_regex

    clear_settings_cache()
