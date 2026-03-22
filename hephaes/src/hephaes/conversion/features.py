from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models import FieldSourceSpec, FeatureSpec


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


def resolve_source_value(payload: Any, source: FieldSourceSpec) -> Any:
    return resolve_field_path(payload, source.field_path)


@dataclass(frozen=True)
class FeatureBuilder:
    def extract(self, payload: Any, feature: FeatureSpec) -> Any:
        return resolve_source_value(payload, feature.source)
