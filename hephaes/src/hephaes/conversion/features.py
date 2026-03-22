from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .transforms import apply_transform_chain
from ..models import FeatureSourceSpec, FieldSourceSpec, FeatureSpec


def resolve_field_path(payload: Any, field_path: str | None) -> Any:
    if field_path is None or not field_path:
        return payload

    current = payload
    for segment in field_path.split("."):
        if isinstance(current, dict):
            if segment not in current:
                raise KeyError(f"missing field segment: {segment}")
            current = current[segment]
            continue
        if isinstance(current, list):
            if not segment.isdigit():
                raise KeyError(f"list segment must be numeric: {segment}")
            index = int(segment)
            try:
                current = current[index]
            except IndexError as exc:
                raise KeyError(f"list index out of range: {segment}") from exc
            continue
        raise KeyError(f"cannot resolve segment '{segment}' from payload type {type(current).__name__}")

    return current


def runtime_source_topic(source: FeatureSourceSpec) -> str:
    if not isinstance(source, FieldSourceSpec):
        raise NotImplementedError(
            f"runtime feature extraction currently supports only path sources; got '{source.kind}'"
        )
    return source.topic


def resolve_source_value(payload: Any, source: FeatureSourceSpec) -> Any:
    if not isinstance(source, FieldSourceSpec):
        raise NotImplementedError(
            f"runtime feature extraction currently supports only path sources; got '{source.kind}'"
        )
    return resolve_field_path(payload, source.field_path)


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


@dataclass(frozen=True)
class FeatureBuilder:
    def extract(self, payload: Any, feature: FeatureSpec) -> Any:
        return resolve_source_value(payload, feature.source)

    def build(self, payload: Any, feature: FeatureSpec) -> Any:
        value = self.extract(payload, feature)
        value = apply_transform_chain(value, feature.transforms)
        _validate_shape(value, feature.shape)
        return value
