"""Shared FastAPI dependencies for backend adapters."""

from __future__ import annotations

from fastapi import Request
from hephaes import Workspace


def get_workspace(request: Request) -> Workspace:
    workspace = getattr(request.app.state, "workspace", None)
    if workspace is None:  # pragma: no cover - defensive startup guard
        raise RuntimeError("workspace is not initialized on app state")
    return workspace
