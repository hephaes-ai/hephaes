from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..models import OutputConfig, ResampleConfig, RosVersion


@dataclass(frozen=True)
class EpisodeContext:
    episode_id: str
    source_path: Path
    ros_version: RosVersion
    field_names: list[str]
    resample: ResampleConfig | None
    output: OutputConfig


@dataclass(frozen=True)
class RecordBatch:
    timestamps: list[int]
    field_data: dict[str, list[Any | None]]

    @property
    def row_count(self) -> int:
        return len(self.timestamps)


class DatasetWriter(Protocol):
    path: Path

    def write_batch(self, batch: RecordBatch) -> None:
        ...

    def close(self) -> None:
        ...

    def __enter__(self) -> "DatasetWriter":
        ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        ...


class BaseDatasetWriter:
    path: Path

    def __enter__(self) -> "BaseDatasetWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
