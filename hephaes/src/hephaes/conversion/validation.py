from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models import ConversionSpec
from .assembly import ConstructedRowRecord
from .features import FeatureBuilder, runtime_source_topic


@dataclass(frozen=True)
class ValidationSummary:
    checked_records: int
    bad_records: int
    missing_feature_counts: dict[str, int]
    missing_topic_counts: dict[str, int]


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

    sample_n = validation.sample_n if validation.sample_n is not None else len(records)
    sampled_records = records[:sample_n]
    feature_builder = FeatureBuilder()
    missing_feature_counts = {feature_name: 0 for feature_name in spec.features}
    missing_topic_counts: dict[str, int] = {}
    bad_records = 0

    for record in sampled_records:
        record_bad = False
        for feature_name, feature in spec.features.items():
            source_topic = runtime_source_topic(feature.source)
            source_payload = record.values.get(source_topic)
            source_present = record.presence.get(source_topic, 0)

            if source_present == 0:
                missing_topic_counts[source_topic] = missing_topic_counts.get(source_topic, 0) + 1

            if source_payload is None:
                missing_feature_counts[feature_name] += 1
                if feature.required and feature.missing != "zeros":
                    record_bad = True
                continue

            try:
                feature_builder.build(source_payload, feature)
            except Exception:
                missing_feature_counts[feature_name] += 1
                record_bad = True

        if not record_bad:
            continue

        bad_records += 1
        if validation.fail_fast:
            raise ValueError(
                f"validation failed for trigger record at {record.timestamp_ns}"
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
    )


def validate_trigger_records(
    *,
    spec: ConversionSpec,
    records: list[ConstructedRowRecord],
) -> ValidationSummary:
    return validate_constructed_rows(spec=spec, records=records)
