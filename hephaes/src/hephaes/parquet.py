import base64
import json
from pathlib import Path
from typing import Any, Generator, Sequence

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
    def __init__(
        self,
        *,
        output_dir: str | Path,
        episode_id: str,
        field_names: list[str],
        compression: str = "none",
    ) -> None:
        _require_pyarrow()
        self._pa = pa
        self._pq = pq
        self._field_names = list(field_names)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        self.path = output_path / f"{episode_id}.parquet"

        fixed_fields = [
            pa.field("timestamp_ns", pa.int64()),
        ]
        dynamic_fields = [
            pa.field(name, pa.string(), nullable=True)
            for name in self._field_names
        ]
        self._schema = pa.schema(fixed_fields + dynamic_fields)
        writer_compression = None if compression == "none" else compression
        self._writer = pq.ParquetWriter(
            str(self.path),
            self._schema,
            compression=writer_compression,
        )

    def write_table(
        self,
        *,
        timestamps: list[int],
        field_data: dict[str, list[str | None]],
    ) -> None:
        row_count = len(timestamps)
        if row_count == 0:
            return

        arrays: dict[str, Any] = {
            "timestamp_ns": self._pa.array(timestamps, type=pa.int64()),
        }
        for name in self._field_names:
            col_values = field_data.get(name, [None] * row_count)
            arrays[name] = self._pa.array(col_values, type=pa.string())

        table = self._pa.table(arrays, schema=self._schema)
        self._writer.write_table(table)

    def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            self._writer = None

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
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")

    _require_pyarrow()
    parquet_file = pq.ParquetFile(str(parquet_path))
    for batch in parquet_file.iter_batches(batch_size=batch_size, columns=columns):
        yield from batch.to_pylist()


def _find_base64_payloads(value: Any) -> list[str]:
    payloads: list[str] = []

    if isinstance(value, dict):
        if value.get("__bytes__") is True:
            encoding = value.get("encoding")
            encoded = value.get("value")
            if encoding == "base64" and isinstance(encoded, str):
                payloads.append(encoded)

        for child in value.values():
            payloads.extend(_find_base64_payloads(child))
        return payloads

    if isinstance(value, list):
        for child in value:
            payloads.extend(_find_base64_payloads(child))

    return payloads


def extract_images(
    parquet_path: str | Path,
    column: str,
    *,
    batch_size: int = 1024,
) -> list[bytes]:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")

    _require_pyarrow()
    parquet_file = pq.ParquetFile(str(parquet_path))
    if column not in parquet_file.schema.names:
        raise ValueError(f"column '{column}' not found in parquet file")

    images: list[bytes] = []
    for row in stream_wide_parquet_rows(
        parquet_path,
        columns=[column],
        batch_size=batch_size,
    ):
        cell = row.get(column)
        if cell is None:
            continue

        payload_obj: Any = cell
        if isinstance(cell, str):
            try:
                payload_obj = json.loads(cell)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"column '{column}' contains non-JSON string payloads; "
                    "expected JSON-encoded base64 bytes"
                ) from exc

        for encoded in _find_base64_payloads(payload_obj):
            try:
                images.append(base64.b64decode(encoded, validate=True))
            except (ValueError, base64.binascii.Error) as exc:
                raise ValueError(
                    f"column '{column}' contains invalid base64 payload"
                ) from exc

    return images
