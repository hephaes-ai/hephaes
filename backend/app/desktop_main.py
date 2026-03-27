"""Desktop entrypoint for the packaged FastAPI backend."""

from __future__ import annotations

import argparse
import os
from typing import Sequence

import uvicorn

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
        log_level=args.log_level,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
