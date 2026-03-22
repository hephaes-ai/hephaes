from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from .._converter_helpers import _normalize_payload
from ..models import DecodeFailurePolicy, FeatureDType

FieldKind = Literal["scalar", "sequence", "struct", "bytes", "image", "unknown"]


class InspectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topics: list[str] = Field(default_factory=list)
    sample_n: int = Field(default=8, ge=1)
    max_depth: int = Field(default=4, ge=0)
    max_sequence_items: int = Field(default=4, ge=1)
    on_failure: DecodeFailurePolicy = "warn"
    topic_type_hints: dict[str, str] = Field(default_factory=dict)


class SampledMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: int = Field(ge=0)
    payload: Any


class FieldCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    kind: FieldKind = "unknown"
    examples: list[Any] = Field(default_factory=list)
    nullable: bool = False
    candidate_dtypes: list[FeatureDType] = Field(default_factory=list)
    shape_hint: list[int] | None = None
    variable_length: bool = False
    image_like: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)


class TopicInspectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    message_type: str | None = None
    sampled_message_count: int = 0
    sample_timestamps: list[int] = Field(default_factory=list)
    sample_payloads: list[SampledMessage] = Field(default_factory=list)
    top_level_summary: dict[str, Any] = Field(default_factory=dict)
    field_candidates: dict[str, FieldCandidate] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class InspectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bag_path: str | None = None
    ros_version: str | None = None
    sample_n: int = Field(default=8, ge=1)
    topics: dict[str, TopicInspectionResult] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


@dataclass
class _FieldStats:
    path: str
    examples: list[Any] = field(default_factory=list)
    observed_kinds: set[str] = field(default_factory=set)
    observed_scalar_kinds: set[str] = field(default_factory=set)
    observed_shapes: list[list[int]] = field(default_factory=list)
    null_count: int = 0
    count: int = 0
    image_like_hits: int = 0
    warnings: set[str] = field(default_factory=set)


def _scalar_kind(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        return "int"
    if isinstance(value, (float, np.floating)):
        return "float"
    if isinstance(value, (bytes, bytearray)):
        return "bytes"
    if isinstance(value, str):
        return "str"
    return "json"


def _infer_candidate_dtypes(observed_scalar_kinds: set[str], *, image_like: bool) -> list[FeatureDType]:
    if image_like:
        return ["bytes"]
    if not observed_scalar_kinds:
        return ["json"]
    if observed_scalar_kinds <= {"bool"}:
        return ["bool"]
    if observed_scalar_kinds <= {"int"}:
        return ["int64"]
    if observed_scalar_kinds <= {"float"}:
        return ["float32", "float64"]
    if observed_scalar_kinds <= {"int", "float"}:
        return ["float32", "float64"]
    if observed_scalar_kinds <= {"bytes"}:
        return ["bytes"]
    if observed_scalar_kinds <= {"str"}:
        return ["bytes", "json"]
    return ["json"]


def _infer_shape(value: Any, *, max_sequence_items: int) -> list[int] | None:
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        length = len(value)
        if not value:
            return [0]
        child_shapes = [
            _infer_shape(item, max_sequence_items=max_sequence_items)
            for item in value[:max_sequence_items]
        ]
        child_shapes = [shape for shape in child_shapes if shape is not None]
        if not child_shapes:
            return [length]
        first = child_shapes[0]
        if all(shape == first for shape in child_shapes):
            return [length, *first]
        if len(first) == 0:
            return [length]
        return [length, *([-1] * len(first))]
    return None


def _merge_shapes(shapes: list[list[int] | None]) -> list[int] | None:
    filtered = [shape for shape in shapes if shape is not None]
    if not filtered:
        return None
    if len(filtered) == 1:
        return list(filtered[0])

    max_len = max(len(shape) for shape in filtered)
    merged: list[int] = []
    for index in range(max_len):
        dims = {
            shape[index]
            for shape in filtered
            if index < len(shape)
        }
        if not dims:
            merged.append(-1)
        elif len(dims) == 1:
            merged.append(next(iter(dims)))
        else:
            merged.append(-1)
    return merged


def _path_tail(path: str) -> str:
    if not path:
        return ""
    return path.rsplit(".", 1)[-1].lower()


def _is_image_like(path: str, payload: Any, topic: str) -> bool:
    path_lower = path.lower()
    path_tail = _path_tail(path)
    topic_lower = topic.lower()

    if any(token in path_lower for token in ("image", "rgb", "bgr", "rgba", "bgra")):
        return True

    if path_tail in {"data", "pixels", "frame"} and any(
        token in topic_lower for token in ("image", "camera", "rgb", "bgr")
    ):
        return True

    if isinstance(payload, (bytes, bytearray, np.bytes_)):
        return path_tail in {"data", "pixels", "frame", "image"} or any(
            token in topic_lower for token in ("image", "camera", "rgb", "bgr")
        )

    if isinstance(payload, dict):
        keys = {str(key).lower() for key in payload}
        if {"width", "height", "encoding"}.issubset(keys) and path_tail in {"data", "pixels", "frame"}:
            return True
        if {"width", "height", "data"}.issubset(keys) and path_tail in {"data", "pixels", "frame"}:
            return True

    return False


def _summarize_payload(payload: Any, *, max_items: int = 8) -> Any:
    if isinstance(payload, dict):
        keys = list(payload.keys())
        summary: dict[str, Any] = {"kind": "dict", "keys": keys[:max_items]}
        if len(keys) > max_items:
            summary["truncated"] = True
        return summary
    if isinstance(payload, list):
        summary = {"kind": "list", "length": len(payload), "preview": payload[:max_items]}
        if len(payload) > max_items:
            summary["truncated"] = True
        return summary
    return payload


def _observe_value(
    stats_map: dict[str, _FieldStats],
    *,
    path: str,
    value: Any,
    topic: str,
    depth: int,
    max_depth: int,
    max_sequence_items: int,
) -> None:
    if value is None:
        if path:
            stats = stats_map.setdefault(path, _FieldStats(path=path))
            stats.null_count += 1
            stats.count += 1
            if len(stats.examples) < 3:
                stats.examples.append(None)
        return

    if isinstance(value, (bytes, bytearray, np.bytes_)):
        leaf_path = path or "__root__"
        stats = stats_map.setdefault(leaf_path, _FieldStats(path=leaf_path))
        stats.observed_kinds.add("scalar")
        stats.observed_scalar_kinds.add("bytes")
        stats.count += 1
        if len(stats.examples) < 3:
            stats.examples.append(_normalize_payload(value))
        if _is_image_like(leaf_path, value, topic):
            stats.image_like_hits += 1
        return

    if isinstance(value, dict):
        if path:
            stats = stats_map.setdefault(path, _FieldStats(path=path))
            stats.observed_kinds.add("struct")
            stats.count += 1
            if len(stats.examples) < 3:
                stats.examples.append(_summarize_payload(_normalize_payload(value)))
            if _is_image_like(path, value, topic):
                stats.image_like_hits += 1
        if depth >= max_depth:
            if path:
                stats_map.setdefault(path, _FieldStats(path=path)).warnings.add("max depth reached")
            return
        for key, child_value in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            _observe_value(
                stats_map,
                path=child_path,
                value=child_value,
                topic=topic,
                depth=depth + 1,
                max_depth=max_depth,
                max_sequence_items=max_sequence_items,
            )
        return

    if isinstance(value, (list, tuple)):
        if path:
            stats = stats_map.setdefault(path, _FieldStats(path=path))
            stats.observed_kinds.add("sequence")
            stats.count += 1
            stats.observed_shapes.append(
                _infer_shape(value, max_sequence_items=max_sequence_items) or [len(value)]
            )
            if len(stats.examples) < 3:
                stats.examples.append(_summarize_payload(_normalize_payload(value)))
            if _is_image_like(path, value, topic):
                stats.image_like_hits += 1
        if depth >= max_depth:
            if path:
                stats_map.setdefault(path, _FieldStats(path=path)).warnings.add("max depth reached")
            return
        for index, child_value in enumerate(value[:max_sequence_items]):
            if isinstance(child_value, (dict, list, tuple)):
                child_path = f"{path}.{index}" if path else str(index)
                _observe_value(
                    stats_map,
                    path=child_path,
                    value=child_value,
                    topic=topic,
                    depth=depth + 1,
                    max_depth=max_depth,
                    max_sequence_items=max_sequence_items,
                )
                continue
            if child_value is None:
                stats.null_count += 1
                continue
            stats.observed_scalar_kinds.add(_scalar_kind(child_value))
        return

    normalized = _normalize_payload(value)
    if isinstance(normalized, dict):
        _observe_value(
            stats_map,
            path=path,
            value=normalized,
            topic=topic,
            depth=depth,
            max_depth=max_depth,
            max_sequence_items=max_sequence_items,
        )
        return

    if isinstance(normalized, list):
        _observe_value(
            stats_map,
            path=path,
            value=normalized,
            topic=topic,
            depth=depth,
            max_depth=max_depth,
            max_sequence_items=max_sequence_items,
        )
        return

    kind = _scalar_kind(normalized)
    if not path:
        path = "__root__"
    stats = stats_map.setdefault(path, _FieldStats(path=path))
    stats.observed_kinds.add("scalar")
    stats.observed_scalar_kinds.add(kind)
    stats.count += 1
    if len(stats.examples) < 3:
        stats.examples.append(normalized)
    if _is_image_like(path, normalized, topic):
        stats.image_like_hits += 1


def _build_field_candidate(
    *,
    path: str,
    stats: _FieldStats,
    topic: str,
) -> FieldCandidate:
    image_like = stats.image_like_hits > 0
    if image_like and stats.observed_kinds & {"scalar", "sequence"}:
        kind: FieldKind = "image"
    elif "sequence" in stats.observed_kinds:
        kind = "sequence"
    elif "scalar" in stats.observed_kinds:
        kind = "bytes" if stats.observed_scalar_kinds <= {"bytes", "str"} else "scalar"
    elif "struct" in stats.observed_kinds:
        kind = "struct"
    else:
        kind = "unknown"

    shape_hint = _merge_shapes(stats.observed_shapes)
    variable_length = bool(shape_hint and any(dim == -1 for dim in shape_hint))
    if stats.observed_shapes and any(shape != stats.observed_shapes[0] for shape in stats.observed_shapes[1:]):
        stats.warnings.add("observed shape varies across samples")
    candidate_dtypes = _infer_candidate_dtypes(stats.observed_scalar_kinds, image_like=image_like)
    warnings = sorted(stats.warnings)
    if not path:
        warnings.append("root payload candidate")
    confidence = 0.0
    if stats.count > 0:
        observed_modes = len(stats.observed_kinds) + max(1, len(stats.observed_scalar_kinds))
        confidence = min(1.0, max(0.25, 1.0 - 0.15 * max(0, observed_modes - 1)))
        if shape_hint is not None and not variable_length:
            confidence = min(1.0, confidence + 0.1)

    return FieldCandidate(
        path=path,
        kind=kind,
        examples=list(stats.examples),
        nullable=stats.null_count > 0,
        candidate_dtypes=candidate_dtypes,
        shape_hint=shape_hint,
        variable_length=variable_length,
        image_like=image_like,
        confidence=confidence,
        warnings=warnings,
    )


def inspect_reader(
    reader: Any,
    *,
    topics: list[str] | None = None,
    sample_n: int = 8,
    max_depth: int = 4,
    max_sequence_items: int = 4,
    on_failure: DecodeFailurePolicy = "warn",
    topic_type_hints: dict[str, str] | None = None,
) -> InspectionResult:
    if topics is None or not topics:
        available_topics = list(getattr(reader, "topics", {}).keys())
    else:
        available_topics = [topic for topic in topics if topic]

    selected_topics = list(dict.fromkeys(available_topics))
    message_types = getattr(reader, "topics", {}) or {}
    topic_results: dict[str, TopicInspectionResult] = {}
    topic_stats: dict[str, dict[str, _FieldStats]] = {
        topic: defaultdict(lambda: _FieldStats(path="")) for topic in selected_topics
    }
    sample_counts: dict[str, int] = {topic: 0 for topic in selected_topics}
    sampled_messages: dict[str, list[SampledMessage]] = {topic: [] for topic in selected_topics}
    warnings: list[str] = []

    for message in reader.read_messages(
        topics=available_topics,
        on_failure=on_failure,
        topic_type_hints=topic_type_hints or None,
    ):
        if message.topic not in selected_topics:
            continue
        if sample_counts[message.topic] >= sample_n:
            continue

        sample_counts[message.topic] += 1
        topic_stats.setdefault(message.topic, defaultdict(lambda: _FieldStats(path="")))
        topic_stats[message.topic].setdefault("", _FieldStats(path=""))
        sampled_messages[message.topic].append(
            SampledMessage(
                timestamp=int(message.timestamp),
                payload=_summarize_payload(_normalize_payload(message.data)),
            )
        )
        _observe_value(
            topic_stats[message.topic],
            path="",
            value=message.data,
            topic=message.topic,
            depth=0,
            max_depth=max_depth,
            max_sequence_items=max_sequence_items,
        )

    for topic in selected_topics:
        stats_map = topic_stats.get(topic, {})
        candidates: dict[str, FieldCandidate] = {}
        top_level_summary: dict[str, Any] = {"kind": "unknown", "keys": []}

        root_stats = stats_map.get("")
        if root_stats is not None and root_stats.examples:
            top_level_summary["kind"] = "root"
            top_level_summary["preview"] = root_stats.examples[0]

        for path in sorted(path for path in stats_map.keys() if path):
            field_stats = stats_map[path]
            candidates[path] = _build_field_candidate(path=path, stats=field_stats, topic=topic)

        if not candidates:
            warnings.append(f"no leaf candidates discovered for topic '{topic}'")

        sample_payloads = sampled_messages.get(topic, [])
        sample_timestamps = [sample.timestamp for sample in sample_payloads]
        if top_level_summary.get("kind") == "unknown" and sample_payloads:
            top_level_summary = {
                "kind": "sample",
                "preview": sample_payloads[0].payload,
            }

        topic_results[topic] = TopicInspectionResult(
            topic=topic,
            message_type=message_types.get(topic),
            sampled_message_count=sample_counts.get(topic, 0),
            sample_timestamps=sample_timestamps,
            sample_payloads=sample_payloads,
            top_level_summary=top_level_summary,
            field_candidates=candidates,
            warnings=sorted(
                {
                    warning
                    for field_candidate in candidates.values()
                    for warning in field_candidate.warnings
                }
            ),
        )

    return InspectionResult(
        bag_path=str(getattr(reader, "bag_path", "")) or None,
        ros_version=str(getattr(reader, "ros_version", "")) or None,
        sample_n=sample_n,
        topics=topic_results,
        warnings=warnings,
    )


def inspect_bag(
    bag_path: str | Path,
    *,
    topics: list[str] | None = None,
    sample_n: int = 8,
    max_depth: int = 4,
    max_sequence_items: int = 4,
    on_failure: DecodeFailurePolicy = "warn",
    topic_type_hints: dict[str, str] | None = None,
) -> InspectionResult:
    from ..reader import RosReader

    with RosReader.open(str(bag_path)) as reader:
        return inspect_reader(
            reader,
            topics=topics,
            sample_n=sample_n,
            max_depth=max_depth,
            max_sequence_items=max_sequence_items,
            on_failure=on_failure,
            topic_type_hints=topic_type_hints,
        )
