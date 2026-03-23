from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .introspection import FieldCandidate, InspectionResult
from .preview import PreviewResult, preview_conversion_spec
from ..models import (
    AssemblySpec,
    ConversionSpec,
    DecodingSpec,
    DraftOriginSpec,
    FieldSourceSpec,
    FeatureSpec,
    InputDiscoverySpec,
    LabelSpec,
    JoinSpec,
    OutputSpec,
    SchemaSpec,
    TopicDecodeSpec,
    TransformSpec,
    ValidationSpec,
)

OutputFormat = Literal["parquet", "tfrecord"]


class DraftSpecRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger_topic: str | None = None
    selected_topics: list[str] = Field(default_factory=list)
    join_topics: list[str] = Field(default_factory=list)
    schema_name: str = Field(default="draft_conversion", min_length=1)
    schema_version: int = Field(default=1, ge=1)
    output_format: OutputFormat = "tfrecord"
    output_compression: str = "none"
    max_features_per_topic: int = Field(default=2, ge=1)
    label_feature: str | None = None
    include_preview: bool = True
    preview_rows: int = Field(default=5, ge=1)


class DraftSpecResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: DraftSpecRequest
    spec: ConversionSpec
    selected_topics: list[str] = Field(default_factory=list)
    trigger_topic: str | None = None
    join_topics: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    preview: PreviewResult | None = None

    @property
    def preview_ready(self) -> bool:
        return self.preview is not None and bool(self.preview.rows)


def _sanitize_feature_name(value: str) -> str:
    candidate = value.strip("/").replace("/", "_")
    candidate = re.sub(r"[^a-zA-Z0-9]+", "_", candidate).strip("_").lower()
    return candidate or "feature"


def _choose_trigger_topic(
    inspection: InspectionResult,
    selected_topics: list[str],
) -> str | None:
    if not selected_topics:
        return None

    best_topic: str | None = None
    best_score: tuple[int, int, int] | None = None

    for topic in selected_topics:
        topic_result = inspection.topics.get(topic)
        if topic_result is None:
            continue

        image_like_count = sum(
            1 for candidate in topic_result.field_candidates.values() if candidate.image_like
        )
        candidate_count = len(topic_result.field_candidates)
        score = (image_like_count, candidate_count, topic_result.sampled_message_count)
        if best_score is None or score > best_score:
            best_score = score
            best_topic = topic

    return best_topic or selected_topics[0]


def _candidate_priority(candidate: FieldCandidate) -> tuple[int, int, float, int]:
    path_tail = candidate.path.rsplit(".", 1)[-1].lower() if candidate.path else ""
    metadata_names = {"width", "height", "encoding", "format", "step", "stride", "channels"}

    if path_tail in {"data", "pixels", "frame"} and candidate.kind in {"bytes", "scalar", "sequence", "image"}:
        base = 0
    elif candidate.path.endswith("buttons"):
        base = 1
    elif candidate.path.endswith("axes"):
        base = 2
    elif candidate.kind == "bytes":
        base = 3
    elif candidate.kind == "sequence":
        base = 4
    elif candidate.kind == "scalar":
        base = 5
    else:
        base = 6
    if candidate.image_like and path_tail in metadata_names:
        base += 10
    path_length = len(candidate.path.split(".")) if candidate.path else 0
    return (base, -path_length, -candidate.confidence, len(candidate.examples))


def _infer_feature_dtype(candidate: FieldCandidate) -> str:
    if candidate.image_like:
        return "bytes"
    if candidate.candidate_dtypes:
        preferred = candidate.candidate_dtypes[0]
        if candidate.path.endswith("axes") and "float32" in candidate.candidate_dtypes:
            return "float32"
        if candidate.path.endswith("buttons") and "int64" in candidate.candidate_dtypes:
            return "int64"
        if preferred == "bytes" and len(candidate.candidate_dtypes) > 1:
            return "json"
        return preferred
    if candidate.kind == "bytes":
        return "bytes"
    if candidate.kind == "sequence":
        return "json"
    return "json"


def _feature_transforms(candidate: FieldCandidate, dtype: str) -> list[TransformSpec]:
    transforms: list[TransformSpec] = []

    if candidate.kind == "sequence" and candidate.shape_hint:
        exact_length = candidate.shape_hint[0]
        if exact_length >= 0:
            transforms.append(TransformSpec(kind="length", params={"exact": exact_length}))
    if dtype in {"int64", "float32", "float64", "bool"}:
        transforms.append(TransformSpec(kind="cast", params={"dtype": dtype}))

    return transforms


def _build_feature_spec(
    *,
    topic: str,
    candidate: FieldCandidate,
    used_names: set[str],
    required: bool,
) -> tuple[str, FeatureSpec]:
    path_tail = candidate.path.rsplit(".", 1)[-1].lower() if candidate.path else ""

    if candidate.image_like and path_tail in {"data", "pixels", "frame"}:
        candidate_name = "image"
    elif candidate.path.endswith("buttons"):
        candidate_name = "buttons"
    elif candidate.path.endswith("axes"):
        candidate_name = "axes"
    elif candidate.path:
        candidate_name = candidate.path.replace(".", "_")
    else:
        candidate_name = topic

    feature_name = _sanitize_feature_name(candidate_name)
    suffix = 2
    while feature_name in used_names:
        feature_name = f"{_sanitize_feature_name(candidate_name)}_{suffix}"
        suffix += 1
    used_names.add(feature_name)

    dtype = _infer_feature_dtype(candidate)
    shape = candidate.shape_hint if candidate.kind in {"sequence", "image"} else None
    missing = "zeros" if dtype in {"int64", "float32", "float64", "bool"} else "default"
    feature = FeatureSpec(
        source=FieldSourceSpec(topic=topic, field_path=candidate.path or None),
        dtype=dtype,  # type: ignore[arg-type]
        shape=shape,
        required=required,
        missing=missing,  # type: ignore[arg-type]
        transforms=_feature_transforms(candidate, dtype),
        description=None,
    )
    return feature_name, feature


def build_draft_conversion_spec(
    inspection: InspectionResult,
    *,
    request: DraftSpecRequest | None = None,
    reader: Any | None = None,
) -> DraftSpecResult:
    draft_request = request or DraftSpecRequest()
    selected_topics = (
        [topic for topic in draft_request.selected_topics if topic in inspection.topics]
        if draft_request.selected_topics
        else list(inspection.topics.keys())
    )
    if not selected_topics:
        raise ValueError("inspection result does not contain any topics to draft")

    trigger_topic = draft_request.trigger_topic
    if trigger_topic is not None and trigger_topic not in inspection.topics:
        raise ValueError(f"trigger topic not found in inspection result: {trigger_topic}")
    if trigger_topic is None:
        trigger_topic = _choose_trigger_topic(inspection, selected_topics)

    assert trigger_topic is not None

    if trigger_topic not in selected_topics:
        selected_topics = [trigger_topic, *selected_topics]

    join_topics = (
        [topic for topic in draft_request.join_topics if topic in inspection.topics and topic != trigger_topic]
        if draft_request.join_topics
        else [topic for topic in selected_topics if topic != trigger_topic]
    )
    join_topics = list(dict.fromkeys(join_topics))
    selected_topics = list(dict.fromkeys([*selected_topics, *join_topics]))

    used_feature_names: set[str] = set()
    features: dict[str, FeatureSpec] = {}
    warnings: list[str] = []
    assumptions: list[str] = [
        f"drafted from inspection of {len(selected_topics)} selected topics",
        "heuristics were derived from sampled payloads and should be reviewed",
    ]
    unresolved_fields: list[str] = []
    decoding_topics: dict[str, TopicDecodeSpec] = {}

    for topic in selected_topics:
        topic_result = inspection.topics[topic]
        if topic_result.message_type:
            decoding_topics[topic] = TopicDecodeSpec(type_hint=topic_result.message_type)

        candidate_items = sorted(
            topic_result.field_candidates.items(),
            key=lambda item: _candidate_priority(item[1]),
        )
        selected_candidates = candidate_items[: draft_request.max_features_per_topic]
        if not selected_candidates:
            unresolved_fields.append(topic)
            feature_name, feature = _build_feature_spec(
                topic=topic,
                candidate=FieldCandidate(
                    path="",
                    kind="json",
                    candidate_dtypes=["json"],
                    examples=[],
                    confidence=0.25,
                ),
                used_names=used_feature_names,
                required=topic == trigger_topic,
            )
            features[feature_name] = feature
            continue

        for _, candidate in selected_candidates:
            feature_name, feature = _build_feature_spec(
                topic=topic,
                candidate=candidate,
                used_names=used_feature_names,
                required=topic == trigger_topic,
            )
            features[feature_name] = feature

    if not features:
        raise ValueError("drafting failed because no features could be inferred")

    if draft_request.label_feature is not None:
        if draft_request.label_feature not in features:
            unresolved_fields.append(draft_request.label_feature)
            warnings.append(
                f"requested label feature '{draft_request.label_feature}' was not found in drafted features"
            )
            labels = None
        else:
            labels = LabelSpec(
                primary=draft_request.label_feature,
                source=features[draft_request.label_feature].source,
            )
    else:
        labels = None

    assembly = AssemblySpec(
        trigger_topic=trigger_topic,
        joins=[
            JoinSpec(topic=topic, sync_policy="last-known-before", required=False)
            for topic in join_topics
        ],
    )

    spec = ConversionSpec(
        schema_spec=SchemaSpec(name=draft_request.schema_name, version=draft_request.schema_version),
        input=InputDiscoverySpec(include_topics=selected_topics),
        decoding=DecodingSpec(topics=decoding_topics, on_decode_failure="warn"),
        assembly=assembly,
        features=features,
        labels=labels,
        validation=ValidationSpec(
            sample_n=32,
            fail_fast=False,
            expected_features=list(features.keys()),
            preview=False,
        ),
        output=OutputSpec(
            format=draft_request.output_format,
            compression=draft_request.output_compression,  # type: ignore[arg-type]
            shards=1,
        ),
    )

    preview: PreviewResult | None = None
    if draft_request.include_preview:
        if reader is None:
            warnings.append("preview was requested but no reader was provided")
        else:
            try:
                preview = preview_conversion_spec(
                    reader,
                    spec,
                    sample_n=draft_request.preview_rows,
                    topic_type_hints={
                        topic: topic_spec.type_hint
                        for topic, topic_spec in spec.decoding.topics.items()
                        if topic_spec.type_hint is not None
                    },
                )
            except Exception as exc:
                warnings.append(f"preview generation failed: {exc}")

    if trigger_topic is None:
        warnings.append("trigger topic was inferred from inspection")
    if join_topics:
        assumptions.append(f"joined {len(join_topics)} non-trigger topic(s) into each record")

    spec.draft_origin = DraftOriginSpec(
        kind="inspection",
        source_topics=selected_topics,
        provenance={
            "trigger_topic": trigger_topic,
            "join_topics": join_topics,
            "selected_topics": selected_topics,
            "max_features_per_topic": draft_request.max_features_per_topic,
        },
        assumptions=assumptions,
        warnings=warnings,
    )

    return DraftSpecResult(
        request=draft_request,
        spec=spec,
        selected_topics=selected_topics,
        trigger_topic=trigger_topic,
        join_topics=join_topics,
        warnings=warnings,
        assumptions=assumptions,
        unresolved_fields=unresolved_fields,
        preview=preview,
    )
