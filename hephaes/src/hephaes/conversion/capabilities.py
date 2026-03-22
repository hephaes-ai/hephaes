from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..models import (
    DecodeFailurePolicy,
    FeatureDType,
    MissingDataPolicy,
    ParquetCompression,
    ResampleStrategy,
    SyncPolicy,
    TFRecordCompression,
    TFRecordNullEncoding,
    TFRecordPayloadEncoding,
)


FeatureSourceKind = str
RowStrategyKind = str


def _supported_transform_kinds() -> list[str]:
    return [
        "cast",
        "clamp",
        "length",
        "multi_hot",
        "normalize",
        "one_hot",
        "scale",
        "image_color_convert",
        "image_crop",
        "image_encode",
        "image_resize",
    ]


class ConversionCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spec_version: int = Field(default=2, ge=1)
    supports_spec_documents: bool = True
    supports_inspection: bool = True
    supports_draft_generation: bool = True
    supports_preview: bool = True
    supports_migration: bool = True
    row_strategies: list[RowStrategyKind] = Field(default_factory=lambda: ["trigger"])
    authoring_row_strategies: list[RowStrategyKind] = Field(
        default_factory=lambda: ["trigger", "per-message", "resample"]
    )
    planned_row_strategies: list[RowStrategyKind] = Field(
        default_factory=lambda: ["per-message", "resample"]
    )
    feature_source_kinds: list[FeatureSourceKind] = Field(default_factory=lambda: ["path"])
    authoring_feature_source_kinds: list[FeatureSourceKind] = Field(
        default_factory=lambda: ["path", "constant", "metadata", "concat", "stack"]
    )
    planned_feature_source_kinds: list[FeatureSourceKind] = Field(
        default_factory=lambda: ["constant", "metadata", "concat", "stack"]
    )
    feature_dtypes: list[FeatureDType] = Field(
        default_factory=lambda: ["bytes", "int64", "float32", "float64", "bool", "json"]
    )
    sync_policies: list[SyncPolicy] = Field(
        default_factory=lambda: ["nearest", "last-known-before", "exact-within-tolerance"]
    )
    missing_data_policies: list[MissingDataPolicy] = Field(
        default_factory=lambda: ["default", "zeros", "forward_fill", "drop", "error"]
    )
    decode_failure_policies: list[DecodeFailurePolicy] = Field(default_factory=lambda: ["skip", "warn", "fail"])
    resample_strategies: list[ResampleStrategy] = Field(default_factory=lambda: ["interpolate", "downsample"])
    output_formats: list[str] = Field(default_factory=lambda: ["parquet", "tfrecord"])
    parquet_compressions: list[ParquetCompression] = Field(
        default_factory=lambda: ["none", "snappy", "gzip", "brotli", "lz4", "zstd"]
    )
    tfrecord_compressions: list[TFRecordCompression] = Field(default_factory=lambda: ["none", "gzip"])
    tfrecord_payload_encodings: list[TFRecordPayloadEncoding] = Field(default_factory=lambda: ["typed_features"])
    tfrecord_null_encodings: list[TFRecordNullEncoding] = Field(default_factory=lambda: ["presence_flag"])
    transform_kinds: list[str] = Field(default_factory=_supported_transform_kinds)


def build_conversion_capabilities() -> ConversionCapabilities:
    return ConversionCapabilities()
