from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .assembly import assemble_trigger_records
from .features import FeatureBuilder, runtime_source_topic
from ..models import ConversionSpec


class PreviewRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp_ns: int
    field_data: dict[str, Any | None] = Field(default_factory=dict)
    presence_data: dict[str, int] = Field(default_factory=dict)


class PreviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[PreviewRow] = Field(default_factory=list)
    dropped_count: int = 0
    warnings: list[str] = Field(default_factory=list)


def preview_conversion_spec(
    reader: Any,
    spec: ConversionSpec,
    *,
    sample_n: int = 5,
    topic_type_hints: dict[str, str] | None = None,
) -> PreviewResult:
    if sample_n < 1:
        raise ValueError("sample_n must be >= 1")
    if spec.assembly is None:
        raise ValueError("preview requires a schema-aware conversion spec with an assembly section")
    if not spec.assembly.trigger_topic:
        raise ValueError("preview requires a trigger topic")
    if not spec.features:
        raise ValueError("preview requires feature definitions")

    hint_map = {
        topic: topic_spec.type_hint
        for topic, topic_spec in spec.decoding.topics.items()
        if topic_spec.type_hint is not None
    }
    if topic_type_hints:
        hint_map.update(topic_type_hints)

    records, dropped_count = assemble_trigger_records(
        reader=reader,
        trigger_topic=spec.assembly.trigger_topic,
        joins=spec.assembly.joins,
        on_failure=spec.decoding.on_decode_failure,
        topic_type_hints=hint_map or None,
    )

    feature_builder = FeatureBuilder()
    rows: list[PreviewRow] = []
    warnings: list[str] = []

    for record in records[:sample_n]:
        row_values: dict[str, Any | None] = {}
        row_presence: dict[str, int] = {}
        for feature_name, feature in spec.features.items():
            source_topic = runtime_source_topic(feature.source)
            topic_presence = record.presence.get(source_topic, 0)
            if topic_presence == 0:
                row_values[feature_name] = None
                row_presence[feature_name] = 0
                continue

            source_payload = record.values.get(source_topic)
            if source_payload is None:
                row_values[feature_name] = None
                row_presence[feature_name] = 0
                continue

            try:
                extracted_value = feature_builder.build(source_payload, feature)
            except Exception as exc:
                row_values[feature_name] = None
                row_presence[feature_name] = 0
                warnings.append(
                    f"failed to build preview feature '{feature_name}' from topic '{source_topic}': {exc}"
                )
                continue

            row_values[feature_name] = extracted_value
            row_presence[feature_name] = 1

        rows.append(
            PreviewRow(
                timestamp_ns=int(record.timestamp_ns),
                field_data=row_values,
                presence_data=row_presence,
            )
        )

    return PreviewResult(rows=rows, dropped_count=dropped_count, warnings=warnings)
