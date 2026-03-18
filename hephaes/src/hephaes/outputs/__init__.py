from __future__ import annotations

from .base import BaseDatasetWriter, DatasetWriter, EpisodeContext, RecordBatch
from .parquet_writer import ParquetDatasetWriter, create_parquet_writer
from .registry import WriterRegistry
from .tfrecord_writer import TFRecordDatasetWriter, create_tfrecord_writer

DEFAULT_WRITER_REGISTRY = WriterRegistry()
DEFAULT_WRITER_REGISTRY.register("parquet", create_parquet_writer)
DEFAULT_WRITER_REGISTRY.register("tfrecord", create_tfrecord_writer)

__all__ = [
    "BaseDatasetWriter",
    "DatasetWriter",
    "EpisodeContext",
    "RecordBatch",
    "WriterRegistry",
    "ParquetDatasetWriter",
    "TFRecordDatasetWriter",
    "DEFAULT_WRITER_REGISTRY",
]
