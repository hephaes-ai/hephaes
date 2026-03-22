from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models import ConversionSpec, FeatureSpec
from .assembly import ConstructedRowRecord
from .features import FeatureBuilder, FeatureEvaluationContext, source_input_topics


@dataclass(frozen=True)
class ValidationSummary:
    checked_records: int
    bad_records: int
    missing_feature_counts: dict[str, int]
    missing_topic_counts: dict[str, int]
    label_summary: dict[str, Any] | None = None

    @property
    def missing_feature_rates(self) -> dict[str, float]:
        return {
            name: (count / self.checked_records if self.checked_records else 0.0)
            for name, count in self.missing_feature_counts.items()
        }

    @property
    def missing_topic_rates(self) -> dict[str, float]:
        return {
            name: (count / self.checked_records if self.checked_records else 0.0)
            for name, count in self.missing_topic_counts.items()
        }


def validate_constructed_rows(
    *,
    spec: ConversionSpec,
    records: list[ConstructedRowRecord],
) -> ValidationSummary:
    validation = spec.validation
    missing_expected_features = [
        feature_name
        for feature_name in validation.expected_features
        if feature_name not in spec.features
    ]
    if missing_expected_features:
        raise ValueError(
            "validation expected_features are not defined in the conversion spec: "
            + ", ".join(sorted(missing_expected_features))
        )
    if spec.labels is not None and spec.labels.primary is not None and spec.labels.primary not in spec.features:
        raise ValueError(
            f"label primary feature '{spec.labels.primary}' is not defined in the conversion spec"
        )

    sample_n = validation.sample_n if validation.sample_n is not None else len(records)
    sampled_records = records[:sample_n]
    feature_builder = FeatureBuilder()
    missing_feature_counts = {feature_name: 0 for feature_name in spec.features}
    missing_topic_counts: dict[str, int] = {}
    bad_records = 0
    label_feature: FeatureSpec | None = None
    if spec.labels is not None and spec.labels.source is not None:
        label_feature = FeatureSpec(
            source=spec.labels.source,
            dtype="json",
            transforms=spec.labels.transforms,
        )
    label_present_count = 0
    label_missing_count = 0
    label_sample_values: list[Any] = []

    for record in sampled_records:
        record_bad = False
        context = FeatureEvaluationContext.from_row(
            timestamp_ns=int(record.timestamp_ns),
            values=record.values,
            presence=record.presence,
        )
        built_feature_values: dict[str, Any] = {}
        for feature_name, feature in spec.features.items():
            for source_topic in source_input_topics(feature.source):
                source_present = record.presence.get(source_topic, 0)
                if source_present == 0 or record.values.get(source_topic) is None:
                    missing_topic_counts[source_topic] = missing_topic_counts.get(source_topic, 0) + 1

            try:
                feature_value = feature_builder.build(context, feature)
            except Exception:
                missing_feature_counts[feature_name] += 1
                if feature.required and feature.missing != "zeros":
                    record_bad = True
                continue

            built_feature_values[feature_name] = feature_value

        if spec.labels is not None:
            label_value: Any | None = None
            label_present = False
            if spec.labels.primary is not None:
                label_value = built_feature_values.get(spec.labels.primary)
                label_present = label_value is not None
            elif label_feature is not None:
                try:
                    label_value = feature_builder.build(context, label_feature)
                    label_present = label_value is not None
                except Exception:
                    label_present = False

            if label_present:
                label_present_count += 1
                if len(label_sample_values) < 5:
                    label_sample_values.append(label_value)
            else:
                label_missing_count += 1

        if not record_bad:
            continue

        bad_records += 1
        if validation.fail_fast:
            raise ValueError(
                f"validation failed for row at {record.timestamp_ns}"
            )
        if validation.bad_record_budget is not None and bad_records > validation.bad_record_budget:
            raise ValueError(
                f"validation exceeded bad_record_budget of {validation.bad_record_budget}"
            )

    return ValidationSummary(
        checked_records=len(sampled_records),
        bad_records=bad_records,
        missing_feature_counts=missing_feature_counts,
        missing_topic_counts=missing_topic_counts,
        label_summary=(
            {
                "primary": spec.labels.primary if spec.labels is not None else None,
                "present_count": label_present_count,
                "missing_count": label_missing_count,
                "sample_values": label_sample_values,
            }
            if spec.labels is not None
            else None
        ),
    )


def validate_trigger_records(
    *,
    spec: ConversionSpec,
    records: list[ConstructedRowRecord],
) -> ValidationSummary:
    return validate_constructed_rows(spec=spec, records=records)
