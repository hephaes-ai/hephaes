from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .assembly import construct_rows
from .features import FeatureBuilder, FeatureEvaluationContext
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
    if spec.row_strategy is None:
        raise ValueError("preview requires a schema-aware conversion spec with row_strategy")
    if not spec.features:
        raise ValueError("preview requires feature definitions")

    row_result = construct_rows(
        reader=reader,
        spec=spec,
        topic_type_hints=topic_type_hints,
    )

    feature_builder = FeatureBuilder()
    rows: list[PreviewRow] = []
    warnings: list[str] = []

    for record in row_result.records[:sample_n]:
        row_values: dict[str, Any | None] = {}
        row_presence: dict[str, int] = {}
        context = FeatureEvaluationContext.from_row(
            timestamp_ns=int(record.timestamp_ns),
            values=record.values,
            presence=record.presence,
        )
        for feature_name, feature in spec.features.items():
            try:
                extracted_value = feature_builder.build(context, feature)
            except KeyError:
                row_values[feature_name] = None
                row_presence[feature_name] = 0
                continue
            except Exception as exc:
                row_values[feature_name] = None
                row_presence[feature_name] = 0
                warnings.append(
                    f"failed to build preview feature '{feature_name}' from source '{feature.source.kind}': {exc}"
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

    return PreviewResult(rows=rows, dropped_count=row_result.dropped_count, warnings=warnings)
