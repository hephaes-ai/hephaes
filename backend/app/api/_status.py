"""Compatibility helpers for HTTP status constants across Starlette versions."""

from __future__ import annotations

from starlette import status as starlette_status

HTTP_422_UNPROCESSABLE_CONTENT = getattr(
    starlette_status,
    "HTTP_422_UNPROCESSABLE_CONTENT",
    starlette_status.HTTP_422_UNPROCESSABLE_ENTITY,
)
