"""Compatibility helpers for HTTP status constants across Starlette versions."""

from __future__ import annotations

from starlette import status as starlette_status

if hasattr(starlette_status, "HTTP_422_UNPROCESSABLE_CONTENT"):
    HTTP_422_UNPROCESSABLE_CONTENT = starlette_status.HTTP_422_UNPROCESSABLE_CONTENT
else:  # pragma: no cover - compatibility path for older Starlette releases
    HTTP_422_UNPROCESSABLE_CONTENT = starlette_status.HTTP_422_UNPROCESSABLE_ENTITY
