from __future__ import annotations

import gzip
import struct
from pathlib import Path
from typing import Any, BinaryIO, Generator

from ._tfrecord_crc import _masked_crc32c

_SEQUENCE_LENGTH_PREFIX = "__sequence_length__"


def _decode_varint(data: bytes, offset: int) -> tuple[int, int]:
    shift = 0
    value = 0

    while True:
        if offset >= len(data):
            raise ValueError("Malformed TFRecord Example: truncated varint")

        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7


def _iter_message_fields(payload: bytes):
    offset = 0
    while offset < len(payload):
        tag, offset = _decode_varint(payload, offset)
        field_number = tag >> 3
        wire_type = tag & 0x07

        if wire_type == 0:
            value, offset = _decode_varint(payload, offset)
            yield field_number, wire_type, value
            continue

        if wire_type == 2:
            length, offset = _decode_varint(payload, offset)
            end = offset + length
            if end > len(payload):
                raise ValueError("Malformed TFRecord Example: truncated length-delimited field")
            yield field_number, wire_type, payload[offset:end]
            offset = end
            continue

        raise ValueError(f"Unsupported protobuf wire type in TFRecord Example: {wire_type}")


def _decode_signed_int64(value: int) -> int:
    if value >= 1 << 63:
        return value - (1 << 64)
    return value


def _decode_packed_int64(payload: bytes) -> list[int]:
    values: list[int] = []
    offset = 0
    while offset < len(payload):
        value, offset = _decode_varint(payload, offset)
        values.append(_decode_signed_int64(value))
    return values


def _decode_packed_float(payload: bytes) -> list[float]:
    if len(payload) % 4 != 0:
        raise ValueError("Malformed TFRecord Example: invalid packed float payload")
    if not payload:
        return []
    return [item[0] for item in struct.iter_unpack("<f", payload)]


def _decode_feature(payload: bytes) -> tuple[str, list[bytes] | list[int] | list[float]]:
    for field_number, wire_type, value in _iter_message_fields(payload):
        if field_number == 1 and wire_type == 2:
            return "bytes", [
                child
                for child_field_number, child_wire_type, child in _iter_message_fields(value)
                if child_field_number == 1 and child_wire_type == 2
            ]

        if field_number == 2 and wire_type == 2:
            for child_field_number, child_wire_type, child in _iter_message_fields(value):
                if child_field_number == 1 and child_wire_type == 2:
                    return "float", _decode_packed_float(child)

        if field_number == 3 and wire_type == 2:
            for child_field_number, child_wire_type, child in _iter_message_fields(value):
                if child_field_number == 1 and child_wire_type == 2:
                    return "int64", _decode_packed_int64(child)

    raise ValueError("Malformed TFRecord Example: unsupported feature payload")


def _decode_example_features(payload: bytes) -> dict[str, tuple[str, list[bytes] | list[int] | list[float]]]:
    features: dict[str, tuple[str, list[bytes] | list[int] | list[float]]] = {}

    for field_number, wire_type, entry_payload in _iter_message_fields(payload):
        if field_number != 1 or wire_type != 2:
            continue

        key: str | None = None
        feature_payload: bytes | None = None
        for entry_field_number, entry_wire_type, entry_value in _iter_message_fields(entry_payload):
            if entry_field_number == 1 and entry_wire_type == 2:
                key = entry_value.decode("utf-8")
            elif entry_field_number == 2 and entry_wire_type == 2:
                feature_payload = entry_value

        if key is None or feature_payload is None:
            raise ValueError("Malformed TFRecord Example: invalid feature entry")

        features[key] = _decode_feature(feature_payload)

    return features


def _decode_example(payload: bytes) -> dict[str, tuple[str, list[bytes] | list[int] | list[float]]]:
    for field_number, wire_type, value in _iter_message_fields(payload):
        if field_number == 1 and wire_type == 2:
            return _decode_example_features(value)
    raise ValueError("Malformed TFRecord Example: missing features field")


def _collapse_feature_values(kind: str, values: list[bytes] | list[int] | list[float]) -> Any:
    if len(values) == 1:
        return values[0]
    return list(values)


def _extract_sequence_lengths(
    features: dict[str, tuple[str, list[bytes] | list[int] | list[float]]],
) -> dict[str, int]:
    sequence_lengths: dict[str, int] = {}

    for feature_name, (kind, values) in features.items():
        if not feature_name.startswith(_SEQUENCE_LENGTH_PREFIX):
            continue
        if kind != "int64" or len(values) != 1:
            raise ValueError("Malformed TFRecord Example: invalid sequence metadata")

        target_name = feature_name[len(_SEQUENCE_LENGTH_PREFIX):]
        sequence_lengths[target_name] = int(values[0])

    return sequence_lengths


def _read_exact(handle: BinaryIO, size: int) -> bytes:
    data = handle.read(size)
    if len(data) != size:
        raise ValueError("Malformed TFRecord file: truncated record")
    return data


def _open_tfrecord_handle(path: Path) -> BinaryIO:
    with path.open("rb") as raw_handle:
        prefix = raw_handle.read(2)

    if prefix == b"\x1f\x8b":
        return gzip.open(path, "rb")
    return path.open("rb")


def stream_tfrecord_rows(
    tfrecord_path: str | Path,
    *,
    validate_checksums: bool = True,
) -> Generator[dict[str, Any], None, None]:
    path = Path(tfrecord_path)

    with _open_tfrecord_handle(path) as handle:
        while True:
            length_bytes = handle.read(8)
            if not length_bytes:
                return
            if len(length_bytes) != 8:
                raise ValueError("Malformed TFRecord file: truncated length header")

            length_crc = _read_exact(handle, 4)
            if validate_checksums:
                expected_length_crc = struct.pack("<I", _masked_crc32c(length_bytes))
                if length_crc != expected_length_crc:
                    raise ValueError("Malformed TFRecord file: length checksum mismatch")

            payload_length = struct.unpack("<Q", length_bytes)[0]
            payload = _read_exact(handle, payload_length)
            payload_crc = _read_exact(handle, 4)
            if validate_checksums:
                expected_payload_crc = struct.pack("<I", _masked_crc32c(payload))
                if payload_crc != expected_payload_crc:
                    raise ValueError("Malformed TFRecord file: payload checksum mismatch")

            features = _decode_example(payload)
            sequence_lengths = _extract_sequence_lengths(features)
            row: dict[str, Any] = {}

            for feature_name, (kind, values) in features.items():
                if feature_name.startswith(_SEQUENCE_LENGTH_PREFIX):
                    continue

                if feature_name in sequence_lengths:
                    row[feature_name] = list(values)
                    continue

                row[feature_name] = _collapse_feature_values(kind, values)

            for feature_name, sequence_length in sequence_lengths.items():
                if feature_name in row:
                    continue
                if sequence_length != 0:
                    raise ValueError(
                        "Malformed TFRecord Example: sequence metadata without payload"
                    )
                row[feature_name] = []

            yield row
