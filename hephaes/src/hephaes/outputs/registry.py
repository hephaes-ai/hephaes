from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..models import OutputConfig
from .base import DatasetWriter, EpisodeContext

WriterFactory = Callable[..., DatasetWriter]


class WriterRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, WriterFactory] = {}

    def register(self, format_name: str, factory: WriterFactory) -> None:
        self._factories[format_name] = factory

    def resolve(self, format_name: str) -> WriterFactory:
        try:
            return self._factories[format_name]
        except KeyError as exc:
            raise ValueError(f"Unsupported output format: {format_name}") from exc

    def create_writer(
        self,
        *,
        output_dir: str | Path,
        context: EpisodeContext,
        config: OutputConfig,
    ) -> DatasetWriter:
        factory = self.resolve(config.format)
        return factory(output_dir=Path(output_dir), context=context, config=config)

