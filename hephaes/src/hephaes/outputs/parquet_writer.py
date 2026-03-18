from __future__ import annotations

from pathlib import Path
from typing import Any

from .._converter_helpers import JsonPayloadSerializer
from ..models import OutputConfig, ParquetOutputConfig
from ..parquet import WideParquetWriter
from .base import BaseDatasetWriter, EpisodeContext, RecordBatch


class ParquetDatasetWriter(BaseDatasetWriter):
    format_name = "parquet"

    def __init__(
        self,
        *,
        output_dir: str | Path,
        context: EpisodeContext,
        config: ParquetOutputConfig,
    ) -> None:
        self._serializer = JsonPayloadSerializer()
        self._writer = WideParquetWriter(
            output_dir=output_dir,
            episode_id=context.episode_id,
            field_names=context.field_names,
            compression=config.compression,
        )
        self.path = self._writer.path

    def write_batch(self, batch: RecordBatch) -> None:
        serialized_field_data: dict[str, list[str | None]] = {}
        for field_name, values in batch.field_data.items():
            serialized_field_data[field_name] = [
                self._serialize_value(value)
                for value in values
            ]
        self._writer.write_table(
            timestamps=batch.timestamps,
            field_data=serialized_field_data,
        )

    def close(self) -> None:
        self._writer.close()

    def _serialize_value(self, value: Any | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return self._serializer.dumps(value)


def create_parquet_writer(
    *,
    output_dir: Path,
    context: EpisodeContext,
    config: OutputConfig,
) -> ParquetDatasetWriter:
    if not isinstance(config, ParquetOutputConfig):
        raise TypeError("Parquet writer requires a ParquetOutputConfig")

    return ParquetDatasetWriter(
        output_dir=output_dir,
        context=context,
        config=config,
    )
