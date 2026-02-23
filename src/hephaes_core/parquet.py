from pathlib import Path
from typing import Any, Generator, Sequence

from .models import RosVersion

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


class WideParquetWriter:
    """Write a wide-format Parquet file where each mapped field is its own column."""

    def __init__(
        self,
        *,
        output_dir: str | Path,
        episode_id: str,
        field_names: list[str],
    ) -> None:
        _require_pyarrow()
        self._pa = pa
        self._pq = pq
        self._episode_id = episode_id
        self._field_names = list(field_names)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        self.path = output_path / f"{episode_id}.parquet"

        fixed_fields = [
            pa.field("episode_id", pa.string()),
            pa.field("bag_path", pa.string()),
            pa.field("ros_version", pa.string()),
            pa.field("timestamp_ns", pa.int64()),
        ]
        dynamic_fields = [
            pa.field(name, pa.string(), nullable=True)
            for name in self._field_names
        ]
        self._schema = pa.schema(fixed_fields + dynamic_fields)
        self._writer = pq.ParquetWriter(str(self.path), self._schema)

    def write_table(
        self,
        *,
        bag_path: str,
        ros_version: RosVersion,
        timestamps: list[int],
        field_data: dict[str, list[str | None]],
    ) -> None:
        row_count = len(timestamps)
        if row_count == 0:
            return

        arrays: dict[str, Any] = {
            "episode_id": self._pa.array([self._episode_id] * row_count, type=pa.string()),
            "bag_path": self._pa.array([bag_path] * row_count, type=pa.string()),
            "ros_version": self._pa.array([ros_version] * row_count, type=pa.string()),
            "timestamp_ns": self._pa.array(timestamps, type=pa.int64()),
        }
        for name in self._field_names:
            col_values = field_data.get(name, [None] * row_count)
            arrays[name] = self._pa.array(col_values, type=pa.string())

        table = self._pa.table(arrays, schema=self._schema)
        self._writer.write_table(table)

    def close(self) -> None:
        self._writer.close()

    def __enter__(self) -> "WideParquetWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def stream_wide_parquet_rows(
    parquet_path: str | Path,
    *,
    columns: Sequence[str] | None = None,
    batch_size: int = 1024,
) -> Generator[dict[str, Any], None, None]:
    """Stream rows from a wide-format Parquet file as plain dicts."""
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")

    _require_pyarrow()
    parquet_file = pq.ParquetFile(str(parquet_path))
    for batch in parquet_file.iter_batches(batch_size=batch_size, columns=columns):
        yield from batch.to_pylist()
