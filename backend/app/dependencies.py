"""Shared FastAPI dependencies for backend adapters."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from app.db.session import get_db_session as _get_db_session
from hephaes import Workspace


def get_workspace(request: Request) -> Workspace:
    workspace = getattr(request.app.state, "workspace", None)
    if workspace is None:  # pragma: no cover - defensive startup guard
        raise RuntimeError("workspace is not initialized on app state")
    return workspace


def get_db_session(request: Request) -> Generator[Session, None, None]:
    yield from _get_db_session(request)
