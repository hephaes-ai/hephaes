"""Desktop entrypoint for the packaged FastAPI backend."""

from __future__ import annotations

import argparse
import copy
import os
from typing import Sequence

import uvicorn
from uvicorn.config import LOGGING_CONFIG

from app.config import get_settings

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_LOG_LEVEL = "info"


def _parse_port(value: str | None) -> int:
    if value is None or not value.strip():
        return DEFAULT_PORT
    return int(value.strip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Hephaes FastAPI backend for desktop packaging.",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("HEPHAES_BACKEND_HOST", DEFAULT_HOST),
        help="Interface to bind the backend to.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_parse_port(os.environ.get("HEPHAES_BACKEND_PORT")),
        help="Port to bind the backend to.",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("HEPHAES_BACKEND_LOG_LEVEL", DEFAULT_LOG_LEVEL),
        help="Uvicorn log level.",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def build_log_config(log_level: str) -> dict[str, object]:
    settings = get_settings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    backend_log_path = settings.log_dir / "backend.log"
    backend_access_log_path = settings.log_dir / "backend-access.log"
    log_config = copy.deepcopy(LOGGING_CONFIG)
    upper_log_level = log_level.upper()

    log_config["handlers"]["file"] = {
        "class": "logging.FileHandler",
        "encoding": "utf-8",
        "filename": str(backend_log_path),
        "formatter": "default",
    }
    log_config["handlers"]["access_file"] = {
        "class": "logging.FileHandler",
        "encoding": "utf-8",
        "filename": str(backend_access_log_path),
        "formatter": "access",
    }
    log_config["loggers"]["uvicorn"]["handlers"] = ["default", "file"]
    log_config["loggers"]["uvicorn"]["level"] = upper_log_level
    log_config["loggers"]["uvicorn.error"]["handlers"] = ["default", "file"]
    log_config["loggers"]["uvicorn.error"]["level"] = upper_log_level
    log_config["loggers"]["uvicorn.error"]["propagate"] = False
    log_config["loggers"]["uvicorn.access"]["handlers"] = ["access", "access_file"]
    log_config["loggers"]["uvicorn.access"]["level"] = upper_log_level
    log_config["root"] = {
        "handlers": ["default", "file"],
        "level": upper_log_level,
    }
    return log_config


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    os.environ.setdefault("HEPHAES_DESKTOP_MODE", "1")
    os.environ["HEPHAES_BACKEND_HOST"] = args.host
    os.environ["HEPHAES_BACKEND_PORT"] = str(args.port)
    os.environ["HEPHAES_BACKEND_LOG_LEVEL"] = args.log_level

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        log_config=build_log_config(args.log_level),
        log_level=args.log_level,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
