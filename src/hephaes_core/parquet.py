from pathlib import Path
from typing import Any, Generator, Sequence

from .models import ParquetRow, RosVersion

try:
    import pyarrow as pa  # type: ignore
    import pyarrow.parquet as pq  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
    pa = None  # type: ignore[assignment]
    pq = None  # type: ignore[assignment]
    _PYARROW_IMPORT_ERROR = exc
else:
    _PYARROW_IMPORT_ERROR = None


def _require_pyarrow() -> None:
    if pa is None or pq is None:
        raise ModuleNotFoundError(
            "pyarrow is required for parquet support. Install it with "
            "`pip install pyarrow`."
        ) from _PYARROW_IMPORT_ERROR


def _to_arrow_type(pa_module: Any, parquet_type: str) -> Any:
    if parquet_type == "string":
        return pa_module.string()
    if parquet_type == "int64":
        return pa_module.int64()
    raise ValueError(f"Unsupported parquet type mapping: {parquet_type}")


def _schema_from_parquet_row(pa_module: Any) -> Any:
    return pa_module.schema(
        [
            (column_name, _to_arrow_type(pa_module, parquet_type))
            for column_name, parquet_type in ParquetRow.parquet_schema_spec()
        ]
    )


class ParquetWriter:
    def __init__(self, *, output_dir: str | Path, episode_id: str) -> None:
        _require_pyarrow()
        self._pa = pa
        self._pq = pq
        self._episode_id = episode_id

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        self.path = output_path / f"{episode_id}.parquet"
        self._schema = _schema_from_parquet_row(self._pa)
        self._writer = self._pq.ParquetWriter(str(self.path), self._schema)

    def write_batch(
        self,
        *,
        bag_path: str,
        ros_version: RosVersion,
        message_indices: Sequence[int],
        timestamps: Sequence[int],
        topic_names: Sequence[str],
        mapped_fields: Sequence[str],
        topic_types: Sequence[str],
        payload_json: Sequence[str],
    ) -> None:
        row_count = len(message_indices)
        if row_count == 0:
            return

        field_types = {field.name: field.type for field in self._schema}
        table = self._pa.table(
            {
                "episode_id": self._pa.array(
                    [self._episode_id] * row_count,
                    type=field_types["episode_id"],
                ),
                "bag_path": self._pa.array([bag_path] * row_count, type=field_types["bag_path"]),
                "ros_version": self._pa.array([ros_version] * row_count, type=field_types["ros_version"]),
                "message_index": self._pa.array(message_indices, type=field_types["message_index"]),
                "timestamp_ns": self._pa.array(timestamps, type=field_types["timestamp_ns"]),
                "topic": self._pa.array(topic_names, type=field_types["topic"]),
                "field": self._pa.array(mapped_fields, type=field_types["field"]),
                "topic_type": self._pa.array(topic_types, type=field_types["topic_type"]),
                "data_json": self._pa.array(payload_json, type=field_types["data_json"]),
            },
            schema=self._schema,
        )
        self._writer.write_table(table)

    def close(self) -> None:
        self._writer.close()

    def __enter__(self) -> "ParquetWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def stream_parquet_rows(
    parquet_path: str | Path,
    *,
    columns: Sequence[str] | None = None,
    batch_size: int = 1024,
) -> Generator[dict[str, Any], None, None]:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")

    _require_pyarrow()
    parquet_file = pq.ParquetFile(str(parquet_path))
    selected_columns = set(columns) if columns is not None else None
    full_schema = set(ParquetRow.column_names())
    validate_rows = selected_columns is None or full_schema.issubset(selected_columns)

    for batch in parquet_file.iter_batches(batch_size=batch_size, columns=columns):
        for row in batch.to_pylist():
            if validate_rows:
                yield ParquetRow.model_validate(row).model_dump()
            else:
                yield row
