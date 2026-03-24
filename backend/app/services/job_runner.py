"""In-process background runner for backend jobs."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

logger = logging.getLogger(__name__)


class BackendJobRunner:
    """Small wrapper around ThreadPoolExecutor for fire-and-forget jobs."""

    def __init__(self, *, max_workers: int, inline: bool = False) -> None:
        self._inline = inline
        self._executor = None if inline else ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="hephaes-job",
        )

    def submit(
        self,
        description: str,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if self._inline:
            func(*args, **kwargs)
            return

        assert self._executor is not None
        self._executor.submit(self._run, description, func, *args, **kwargs)

    def shutdown(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=False)

    @staticmethod
    def _run(
        description: str,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        try:
            func(*args, **kwargs)
        except Exception:
            logger.exception("Background job failed: %s", description)
