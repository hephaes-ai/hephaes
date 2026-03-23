from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .transforms import apply_transform_chain
from ..models import (
    ConcatSourceSpec,
    ConstantSourceSpec,
    FeatureSourceSpec,
    FeatureSpec,
    FieldSourceSpec,
    MetadataSourceSpec,
    StackSourceSpec,
)


@dataclass(frozen=True)
class FeatureEvaluationContext:
    timestamp_ns: int | None = None
    values: dict[str, Any | None] = field(default_factory=dict)
    presence: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(
        cls,
        *,
        timestamp_ns: int,
        values: dict[str, Any | None],
        presence: dict[str, int],
        metadata: dict[str, Any] | None = None,
    ) -> "FeatureEvaluationContext":
        resolved_metadata = {
            "timestamp_ns": timestamp_ns,
            "present_topics": sorted(topic for topic, present in presence.items() if present),
        }
        if metadata:
            resolved_metadata.update(metadata)
        return cls(
            timestamp_ns=timestamp_ns,
            values=dict(values),
            presence=dict(presence),
            metadata=resolved_metadata,
        )


def resolve_field_path(payload: Any, field_path: str | None) -> Any:
    if field_path is None or not field_path:
        return payload

    current = payload
    for segment in field_path.split("."):
        if isinstance(current, Mapping):
            if segment not in current:
                raise KeyError(f"missing field segment: {segment}")
            current = current[segment]
            continue
        if isinstance(current, (list, tuple)):
            if not segment.isdigit():
                raise KeyError(f"list segment must be numeric: {segment}")
            index = int(segment)
            try:
                current = current[index]
            except IndexError as exc:
                raise KeyError(f"list index out of range: {segment}") from exc
            continue
        try:
            current = getattr(current, segment)
            continue
        except AttributeError as exc:
            raise KeyError(
                f"cannot resolve segment '{segment}' from payload type {type(current).__name__}"
            ) from exc

    return current


def runtime_source_topic(source: FeatureSourceSpec) -> str:
    if not isinstance(source, FieldSourceSpec):
        raise NotImplementedError(
            f"runtime feature extraction currently supports only path sources; got '{source.kind}'"
        )
    return source.topic


def source_input_topics(source: FeatureSourceSpec) -> list[str]:
    return source.input_topics()


def _resolve_path_source(context: Any, source: FieldSourceSpec) -> Any:
    if isinstance(context, FeatureEvaluationContext):
        if context.presence.get(source.topic, 0) == 0:
            raise KeyError(f"missing source topic: {source.topic}")
        payload = context.values.get(source.topic)
        if payload is None:
            raise KeyError(f"missing source topic: {source.topic}")
        return resolve_field_path(payload, source.field_path)

    return resolve_field_path(context, source.field_path)


def _resolve_metadata_source(context: Any, source: MetadataSourceSpec) -> Any:
    if not isinstance(context, FeatureEvaluationContext):
        raise TypeError("metadata sources require feature evaluation context")
    if source.key in context.metadata:
        return context.metadata[source.key]
    if source.default_value is not None:
        return source.default_value
    raise KeyError(f"missing metadata key: {source.key}")


def _coerce_concat_values(values: list[Any], axis: int) -> Any:
    if all(isinstance(value, (bytes, bytearray)) for value in values):
        if axis != 0:
            raise ValueError("byte concatenation only supports axis 0")
        return b"".join(bytes(value) for value in values)

    if all(isinstance(value, str) for value in values):
        if axis != 0:
            raise ValueError("string concatenation only supports axis 0")
        return "".join(values)

    arrays = [value if isinstance(value, np.ndarray) else np.asarray(value) for value in values]
    if any(array.ndim == 0 for array in arrays):
        raise ValueError("concat requires sequence or array values")
    return np.concatenate(arrays, axis=axis)


def _coerce_stack_values(values: list[Any], axis: int) -> Any:
    if any(isinstance(value, (bytes, bytearray, str)) for value in values):
        raise ValueError("stack requires numeric or array-like values")
    arrays = [value if isinstance(value, np.ndarray) else np.asarray(value) for value in values]
    return np.stack(arrays, axis=axis)


def resolve_source_value(context: Any, source: FeatureSourceSpec) -> Any:
    if isinstance(source, FieldSourceSpec):
        return _resolve_path_source(context, source)
    if isinstance(source, ConstantSourceSpec):
        return source.value
    if isinstance(source, MetadataSourceSpec):
        return _resolve_metadata_source(context, source)
    if isinstance(source, ConcatSourceSpec):
        values = [resolve_source_value(context, child) for child in source.sources]
        return _coerce_concat_values(values, source.axis)
    if isinstance(source, StackSourceSpec):
        values = [resolve_source_value(context, child) for child in source.sources]
        return _coerce_stack_values(values, source.axis)
    raise TypeError(f"unsupported feature source type: {type(source).__name__}")


def _validate_shape(value: Any, shape: list[int] | None) -> None:
    if shape is None:
        return
    if not shape:
        return

    if isinstance(value, np.ndarray):
        value = value.tolist()

    if not isinstance(value, (list, tuple)):
        raise ValueError("feature shape validation requires a sequence value")

    expected = shape[0]
    if expected >= 0 and len(value) != expected:
        raise ValueError(f"expected sequence length {expected}, got {len(value)}")
    if expected < 0:
        return

    next_shape = shape[1:]
    for item in value:
        _validate_shape(item, next_shape)


def _coerce_bytes_feature(value: Any) -> Any:
    """Coerce numpy uint8 arrays and uint8 int sequences to bytes."""
    if isinstance(value, (bytes, bytearray)):
        return value
    if isinstance(value, np.ndarray) and value.dtype == np.uint8:
        return value.tobytes()
    if isinstance(value, (list, tuple)):
        try:
            return bytes(value)
        except (TypeError, ValueError, OverflowError):
            return value
    return value


def _normalize_feature_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _validate_scalar_dtype(value: Any, dtype: str) -> None:
    if dtype == "bytes":
        if not isinstance(value, (bytes, bytearray)):
            raise ValueError("expected bytes-compatible feature value")
        return
    if dtype == "bool":
        if not isinstance(value, bool):
            raise ValueError("expected bool feature value")
        return
    if dtype == "int64":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("expected int64-compatible feature value")
        return
    if dtype in {"float32", "float64"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"expected {dtype}-compatible feature value")


def _validate_feature_dtype(value: Any, dtype: str) -> None:
    if dtype == "json":
        return
    if isinstance(value, list):
        for item in value:
            _validate_feature_dtype(item, dtype)
        return
    _validate_scalar_dtype(value, dtype)


@dataclass(frozen=True)
class FeatureBuilder:
    def extract(self, context: Any, feature: FeatureSpec) -> Any:
        return resolve_source_value(context, feature.source)

    def build(self, context: Any, feature: FeatureSpec) -> Any:
        value = self.extract(context, feature)
        value = apply_transform_chain(value, feature.transforms)
        _validate_shape(value, feature.shape)
        if feature.dtype == "bytes":
            value = _coerce_bytes_feature(value)
        value = _normalize_feature_value(value)
        _validate_feature_dtype(value, feature.dtype)
        return value
