from __future__ import annotations

import base64
import gzip
import json
import struct
from pathlib import Path
from typing import Any, BinaryIO

from .._tfrecord_crc import _masked_crc32c
from ..models import OutputConfig, TFRecordOutputConfig
from .base import BaseDatasetWriter, EpisodeContext, RecordBatch

_FeatureValue = tuple[str, list[bytes] | list[int] | list[float]]
_SEQUENCE_LENGTH_PREFIX = "__sequence_length__"


def _encode_varint(value: int) -> bytes:
    if value < 0:
        value &= (1 << 64) - 1

    encoded = bytearray()
    while True:
        to_write = value & 0x7F
        value >>= 7
        if value:
            encoded.append(to_write | 0x80)
        else:
            encoded.append(to_write)
            return bytes(encoded)


def _encode_tag(field_number: int, wire_type: int) -> bytes:
    return _encode_varint((field_number << 3) | wire_type)


def _encode_length_delimited(field_number: int, payload: bytes) -> bytes:
    return _encode_tag(field_number, 2) + _encode_varint(len(payload)) + payload


def _encode_string_field(field_number: int, value: str) -> bytes:
    return _encode_length_delimited(field_number, value.encode("utf-8"))


def _encode_bytes_list(values: list[bytes]) -> bytes:
    payload = b"".join(_encode_length_delimited(1, value) for value in values)
    return _encode_length_delimited(1, payload)


def _encode_float_list(values: list[float]) -> bytes:
    packed = struct.pack("<" + "f" * len(values), *values) if values else b""
    return _encode_length_delimited(2, _encode_length_delimited(1, packed))


def _encode_int64_list(values: list[int]) -> bytes:
    packed = b"".join(_encode_varint(value) for value in values)
    return _encode_length_delimited(3, _encode_length_delimited(1, packed))


def _encode_feature_entry(key: str, payload: bytes) -> bytes:
    entry = _encode_string_field(1, key) + _encode_length_delimited(2, payload)
    return _encode_length_delimited(1, entry)


def _encode_example(features: dict[str, _FeatureValue]) -> bytes:
    entries = bytearray()
    for key, (kind, values) in features.items():
        if kind == "bytes":
            entries.extend(_encode_feature_entry(key, _encode_bytes_list(list(values))))
        elif kind == "float":
            entries.extend(_encode_feature_entry(key, _encode_float_list(list(values))))
        elif kind == "int64":
            entries.extend(_encode_feature_entry(key, _encode_int64_list(list(values))))
        else:  # pragma: no cover - guarded by writer usage
            raise ValueError(f"Unsupported TFRecord feature kind: {kind}")

    return _encode_length_delimited(1, bytes(entries))


def _json_fallback_bytes(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _is_encoded_bytes_object(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("__bytes__") is True
        and value.get("encoding") == "base64"
        and isinstance(value.get("value"), str)
    )


def _decode_encoded_bytes(value: dict[str, Any]) -> bytes:
    return base64.b64decode(value["value"])


def _sequence_length_key(prefix: str) -> str:
    return f"{_SEQUENCE_LENGTH_PREFIX}{prefix}"


def _flatten_sequence_feature(
    prefix: str,
    values: list[Any],
    features: dict[str, _FeatureValue],
) -> None:
    features[_sequence_length_key(prefix)] = ("int64", [len(values)])

    if not values:
        return

    if all(_is_encoded_bytes_object(item) for item in values):
        features[prefix] = (
            "bytes",
            [_decode_encoded_bytes(item) for item in values],
        )
        return

    if all(isinstance(item, bool) for item in values):
        features[prefix] = ("int64", [int(item) for item in values])
        return

    if all(isinstance(item, int) and not isinstance(item, bool) for item in values):
        features[prefix] = ("int64", [int(item) for item in values])
        return

    if all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in values):
        features[prefix] = ("float", [float(item) for item in values])
        return

    if all(isinstance(item, str) for item in values):
        features[prefix] = ("bytes", [item.encode("utf-8") for item in values])
        return

    features[prefix] = ("bytes", [_json_fallback_bytes(values)])


def _flatten_value(
    prefix: str,
    value: Any,
    features: dict[str, _FeatureValue],
) -> None:
    if value is None:
        return

    if _is_encoded_bytes_object(value):
        features[prefix] = ("bytes", [_decode_encoded_bytes(value)])
        return

    if isinstance(value, bool):
        features[prefix] = ("int64", [int(value)])
        return

    if isinstance(value, int):
        features[prefix] = ("int64", [value])
        return

    if isinstance(value, float):
        features[prefix] = ("float", [float(value)])
        return

    if isinstance(value, str):
        features[prefix] = ("bytes", [value.encode("utf-8")])
        return

    if isinstance(value, (list, tuple)):
        _flatten_sequence_feature(prefix, list(value), features)
        return

    if isinstance(value, dict):
        if not value:
            features[prefix] = ("bytes", [_json_fallback_bytes(value)])
            return

        for child_key, child_value in value.items():
            if child_key.startswith("__") and child_key.endswith("__"):
                continue
            _flatten_value(f"{prefix}__{child_key}", child_value, features)
        return

    features[prefix] = ("bytes", [_json_fallback_bytes(value)])


def _row_to_example(
    *,
    timestamp_ns: int,
    row_values: dict[str, Any | None],
    field_names: list[str],
    presence_flags: dict[str, int | None] | None = None,
) -> bytes:
    features: dict[str, _FeatureValue] = {
        "timestamp_ns": ("int64", [timestamp_ns]),
    }

    for field_name in field_names:
        value = row_values.get(field_name)
        present_key = f"{field_name}__present"
        explicit_presence = None if presence_flags is None else presence_flags.get(field_name)

        if explicit_presence is not None:
            features[present_key] = ("int64", [int(explicit_presence)])
            if explicit_presence == 0:
                continue
            if value is None:
                raise ValueError(
                    f"feature '{field_name}' marked present but no value was supplied"
                )
            _flatten_value(field_name, value, features)
            continue

        if value is None:
            features[present_key] = ("int64", [0])
            continue

        features[present_key] = ("int64", [1])
        _flatten_value(field_name, value, features)

    return _encode_example(features)


class TFRecordDatasetWriter(BaseDatasetWriter):
    format_name = "tfrecord"

    def __init__(
        self,
        *,
        output_dir: str | Path,
        context: EpisodeContext,
        config: TFRecordOutputConfig,
    ) -> None:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        self.path = output_path / f"{context.episode_id}.tfrecord"
        self._field_names = list(context.field_names)
        self._handle: BinaryIO
        if config.compression == "gzip":
            self._handle = gzip.open(self.path, "wb")
        else:
            self._handle = self.path.open("wb")

    def write_batch(self, batch: RecordBatch) -> None:
        if batch.row_count == 0:
            return

        for row_index, timestamp_ns in enumerate(batch.timestamps):
            row_values = {
                field_name: values[row_index]
                for field_name, values in batch.field_data.items()
            }
            row_presence = None
            if batch.presence_data is not None:
                row_presence = {
                    field_name: values[row_index]
                    for field_name, values in batch.presence_data.items()
                }
            payload = _row_to_example(
                timestamp_ns=timestamp_ns,
                row_values=row_values,
                field_names=self._field_names,
                presence_flags=row_presence,
            )
            self._write_record(payload)

    def _write_record(self, payload: bytes) -> None:
        length_bytes = struct.pack("<Q", len(payload))
        self._handle.write(length_bytes)
        self._handle.write(struct.pack("<I", _masked_crc32c(length_bytes)))
        self._handle.write(payload)
        self._handle.write(struct.pack("<I", _masked_crc32c(payload)))

    def close(self) -> None:
        self._handle.close()


def create_tfrecord_writer(
    *,
    output_dir: Path,
    context: EpisodeContext,
    config: OutputConfig,
) -> TFRecordDatasetWriter:
    if not isinstance(config, TFRecordOutputConfig):
        raise TypeError("TFRecord writer requires a TFRecordOutputConfig")

    return TFRecordDatasetWriter(
        output_dir=output_dir,
        context=context,
        config=config,
    )
