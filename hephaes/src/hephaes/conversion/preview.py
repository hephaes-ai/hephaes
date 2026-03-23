from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .assembly import construct_rows
from .features import FeatureBuilder, FeatureEvaluationContext
from .validation import validate_constructed_rows
from ..models import ConversionSpec


def _looks_like_raw_image_payload(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and "data" in value
        and "height" in value
        and "width" in value
        and "encoding" in value
    )


def _looks_like_compressed_image_payload(value: Any) -> bool:
    return isinstance(value, dict) and "data" in value and "format" in value


def _contains_ambiguous_image_payload(value: Any) -> bool:
    if isinstance(value, dict):
        if "data" in value:
            image_hint_keys = {"height", "width", "encoding", "format", "step", "is_bigendian"}
            has_image_hints = any(key in value for key in image_hint_keys)
            if (
                has_image_hints
                and not _looks_like_raw_image_payload(value)
                and not _looks_like_compressed_image_payload(value)
            ):
                return True

        return any(_contains_ambiguous_image_payload(child) for child in value.values())

    if isinstance(value, (list, tuple)):
        return any(_contains_ambiguous_image_payload(child) for child in value)

    return False


class PreviewRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp_ns: int
    field_data: dict[str, Any | None] = Field(default_factory=dict)
    presence_data: dict[str, int] = Field(default_factory=dict)


class PreviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[PreviewRow] = Field(default_factory=list)
    dropped_count: int = 0
    checked_records: int = 0
    bad_records: int = 0
    missing_feature_counts: dict[str, int] = Field(default_factory=dict)
    missing_feature_rates: dict[str, float] = Field(default_factory=dict)
    missing_topic_counts: dict[str, int] = Field(default_factory=dict)
    missing_topic_rates: dict[str, float] = Field(default_factory=dict)
    label_summary: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)

    @property
    def preflight_ok(self) -> bool:
        return self.bad_records == 0


def preflight_conversion_spec(
    reader: Any,
    spec: ConversionSpec,
    *,
    sample_n: int | None = None,
    topic_type_hints: dict[str, str] | None = None,
) -> PreviewResult:
    preview_sample_n = 5 if sample_n is None else sample_n
    if preview_sample_n < 1:
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
    validation_summary = validate_constructed_rows(spec=spec, records=row_result.records)

    feature_builder = FeatureBuilder()
    rows: list[PreviewRow] = []
    warnings: list[str] = []
    warned_ambiguous_features: set[str] = set()
    warn_ambiguous_image_payloads = (
        spec.output.format == "tfrecord"
        and spec.output.image_payload_contract == "bytes_v2"
    )

    for record in row_result.records[:preview_sample_n]:
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
            if (
                warn_ambiguous_image_payloads
                and feature_name not in warned_ambiguous_features
                and _contains_ambiguous_image_payload(extracted_value)
            ):
                warnings.append(
                    "ambiguous image-like payload detected for feature "
                    f"'{feature_name}'; expected raw image keys "
                    "(height,width,encoding,data) or compressed image keys (format,data)"
                )
                warned_ambiguous_features.add(feature_name)

        rows.append(
            PreviewRow(
                timestamp_ns=int(record.timestamp_ns),
                field_data=row_values,
                presence_data=row_presence,
            )
        )

    return PreviewResult(
        rows=rows,
        dropped_count=row_result.dropped_count,
        checked_records=validation_summary.checked_records,
        bad_records=validation_summary.bad_records,
        missing_feature_counts=validation_summary.missing_feature_counts,
        missing_feature_rates=validation_summary.missing_feature_rates,
        missing_topic_counts=validation_summary.missing_topic_counts,
        missing_topic_rates=validation_summary.missing_topic_rates,
        label_summary=validation_summary.label_summary,
        warnings=warnings,
    )


def preview_conversion_spec(
    reader: Any,
    spec: ConversionSpec,
    *,
    sample_n: int = 5,
    topic_type_hints: dict[str, str] | None = None,
) -> PreviewResult:
    return preflight_conversion_spec(
        reader,
        spec,
        sample_n=sample_n,
        topic_type_hints=topic_type_hints,
    )
