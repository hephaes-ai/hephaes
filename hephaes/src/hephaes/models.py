from __future__ import annotations

import re
from typing import Annotated, Any, Dict, List, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

CompressionFormat = Literal["zstd", "lz4", "bz2", "none", "unknown"]
ParquetCompression = Literal["none", "snappy", "gzip", "brotli", "lz4", "zstd"]
ResampleMethod = Literal["ffill", "interpolate"]
ResampleStrategy = Literal["interpolate", "downsample"]
RosVersion = Literal["ROS1", "ROS2"]
StorageFormat = Literal["bag", "mcap", "unknown"]
TFRecordCompression = Literal["none", "gzip"]
TFRecordNullEncoding = Literal["presence_flag"]
TFRecordPayloadEncoding = Literal["typed_features"]


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: int = Field(ge=0)
    topic: str = Field(min_length=1)
    data: Any


class InternalStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    compression_format: CompressionFormat


class GroupingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["bag"] = "bag"


class ResampleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    freq_hz: float = Field(gt=0)
    method: ResampleStrategy


class SchemaSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    version: int = Field(ge=1)


class FieldSourceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    field_path: str | None = None

    @field_validator("topic", "field_path", mode="before")
    @classmethod
    def _normalize_non_empty_string(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            return None
        return normalized


class InputDiscoverySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paths: list[str] = Field(default_factory=list)
    recursive: bool = False
    include_topics: list[str] = Field(default_factory=list)
    exclude_topics: list[str] = Field(default_factory=list)
    start_ns: int | None = Field(default=None, ge=0)
    end_ns: int | None = Field(default=None, ge=0)
    max_messages: int | None = Field(default=None, ge=1)
    sample_rate_hz: float | None = Field(default=None, gt=0)

    @field_validator("paths", "include_topics", "exclude_topics")
    @classmethod
    def _normalize_string_list(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise TypeError("values must be strings")
            stripped = item.strip()
            if not stripped:
                raise ValueError("values must be non-empty")
            normalized.append(stripped)
        return normalized

    @model_validator(mode="after")
    def _validate_time_window(self) -> "InputDiscoverySpec":
        if self.start_ns is None or self.end_ns is None:
            return self
        if self.end_ns < self.start_ns:
            raise ValueError("end_ns must be greater than or equal to start_ns")
        return self


DecodeFailurePolicy = Literal["skip", "warn", "fail"]


class TopicDecodeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type_hint: str | None = None
    on_failure: DecodeFailurePolicy = "warn"

    @field_validator("type_hint", mode="before")
    @classmethod
    def _normalize_type_hint(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            return None
        return normalized


class DecodingSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topics: dict[str, TopicDecodeSpec] = Field(default_factory=dict)
    on_decode_failure: DecodeFailurePolicy = "warn"

    @model_validator(mode="after")
    def _validate_topics(self) -> "DecodingSpec":
        for topic in self.topics:
            if not isinstance(topic, str) or not topic.strip():
                raise ValueError("decoding topic names must be non-empty")
        return self


SyncPolicy = Literal["nearest", "last-known-before", "exact-within-tolerance"]
MissingDataPolicy = Literal["default", "zeros", "forward_fill", "drop", "error"]
FeatureDType = Literal["bytes", "int64", "float32", "float64", "bool", "json"]


class JoinSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    sync_policy: SyncPolicy = "last-known-before"
    tolerance_ns: int | None = Field(default=None, ge=0)
    staleness_ns: int | None = Field(default=None, ge=0)
    required: bool = True
    missing: MissingDataPolicy = "default"
    default_value: Any | None = None

    @field_validator("topic", mode="before")
    @classmethod
    def _normalize_topic(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("topic must be non-empty")
        return normalized


def _zero_scalar_for_dtype(dtype: FeatureDType) -> Any | None:
    if dtype == "bytes":
        return b""
    if dtype == "bool":
        return False
    if dtype == "int64":
        return 0
    if dtype in {"float32", "float64"}:
        return 0.0
    return None


def _zero_value_for_shape(shape: list[int], scalar: Any) -> Any:
    if not shape:
        return scalar

    size = shape[0]
    if size < 0:
        return []

    return [_zero_value_for_shape(shape[1:], scalar) for _ in range(size)]


def _assign_default_path(container: dict[str, Any], field_path: str | None, value: Any) -> bool:
    if field_path is None:
        return False

    segments = [segment for segment in field_path.split(".") if segment]
    if not segments:
        return False

    current: dict[str, Any] = container
    for segment in segments[:-1]:
        next_value = current.get(segment)
        if next_value is None:
            next_value = {}
            current[segment] = next_value
        elif not isinstance(next_value, dict):
            return False
        current = next_value

    last_segment = segments[-1]
    existing = current.get(last_segment)
    if existing is not None and existing != value and not isinstance(existing, dict):
        return False
    current[last_segment] = value
    return True


def _build_topic_zero_default(topic: str, features: dict[str, "FeatureSpec"]) -> Any | None:
    topic_features = [
        feature
        for feature in features.values()
        if feature.source.topic == topic and feature.missing == "zeros"
    ]
    if not topic_features:
        return None

    nested_payload: dict[str, Any] = {}
    scalar_payload: Any | None = None
    saw_scalar = False
    saw_nested = False

    for feature in topic_features:
        scalar = _zero_scalar_for_dtype(feature.dtype)
        if scalar is None:
            continue

        value = _zero_value_for_shape(feature.shape, scalar) if feature.shape is not None else scalar
        field_path = feature.source.field_path

        if field_path is None:
            if saw_nested:
                return None
            if saw_scalar and scalar_payload != value:
                return None
            scalar_payload = value
            saw_scalar = True
            continue

        if saw_scalar:
            return None
        if not _assign_default_path(nested_payload, field_path, value):
            return None
        saw_nested = True

    if saw_scalar:
        return scalar_payload
    if nested_payload:
        return nested_payload
    return None


class AssemblySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger_topic: str | None = None
    joins: list[JoinSpec] = Field(default_factory=list)

    @field_validator("trigger_topic", mode="before")
    @classmethod
    def _normalize_trigger_topic(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            return None
        return normalized

    @model_validator(mode="after")
    def _validate_trigger_rules(self) -> "AssemblySpec":
        if self.joins and not self.trigger_topic:
            raise ValueError("trigger_topic must be set when joins are configured")
        return self


class TransformSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_transform_spec(cls, value: object) -> object:
        if isinstance(value, str):
            return {"kind": value, "params": {}}
        if not isinstance(value, dict):
            return value
        if "kind" in value or "params" in value:
            return value
        if len(value) == 1:
            kind, params = next(iter(value.items()))
            if params is None:
                params = {}
            elif not isinstance(params, dict):
                params = {"value": params}
            return {"kind": kind, "params": params}
        return value


class FeatureSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: FieldSourceSpec
    dtype: FeatureDType = "json"
    shape: list[int] | None = None
    required: bool = False
    missing: MissingDataPolicy = "default"
    transforms: list[TransformSpec] = Field(default_factory=list)
    description: str | None = None
    presence_flag: bool = True

    @field_validator("shape")
    @classmethod
    def _validate_shape(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        for dim in value:
            if not isinstance(dim, int):
                raise TypeError("shape dimensions must be integers")
            if dim < -1:
                raise ValueError("shape dimensions must be >= -1")
        return value


class LabelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary: str | None = None
    source: FieldSourceSpec | None = None
    class_map: dict[str, int] = Field(default_factory=dict)
    multi_label: bool = False
    transforms: list[TransformSpec] = Field(default_factory=list)


class SplitSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["none", "time", "random"] = "none"
    train_fraction: float | None = Field(default=None, ge=0, le=1)
    val_fraction: float | None = Field(default=None, ge=0, le=1)
    test_fraction: float | None = Field(default=None, ge=0, le=1)
    seed: int | None = None

    @model_validator(mode="after")
    def _validate_split(self) -> "SplitSpec":
        fractions = [self.train_fraction, self.val_fraction, self.test_fraction]
        provided = [fraction for fraction in fractions if fraction is not None]
        if provided and len(provided) != 3:
            raise ValueError(
                "train_fraction, val_fraction, and test_fraction must all be set together"
            )
        if provided and abs(sum(provided) - 1.0) > 1e-6:
            raise ValueError("train_fraction, val_fraction, and test_fraction must sum to 1")
        return self


class ValidationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_n: int | None = Field(default=None, ge=1)
    fail_fast: bool = False
    bad_record_budget: int | None = Field(default=None, ge=0)
    expected_features: list[str] = Field(default_factory=list)
    preview: bool = False

    @field_validator("expected_features")
    @classmethod
    def _normalize_expected_features(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise TypeError("expected_features values must be strings")
            stripped = item.strip()
            if not stripped:
                raise ValueError("expected_features values must be non-empty")
            normalized.append(stripped)
        return normalized


class OutputSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["parquet", "tfrecord"] = "tfrecord"
    compression: ParquetCompression | TFRecordCompression = "none"
    payload_encoding: TFRecordPayloadEncoding = "typed_features"
    null_encoding: TFRecordNullEncoding = "presence_flag"
    shards: int = Field(default=1, ge=1)
    filename_template: str | None = None
    write_manifest: bool = True

    @model_validator(mode="after")
    def _validate_compression(self) -> "OutputSpec":
        parquet_compressions = {"none", "snappy", "gzip", "brotli", "lz4", "zstd"}
        tfrecord_compressions = {"none", "gzip"}
        if self.format == "parquet" and self.compression not in parquet_compressions:
            raise ValueError("invalid parquet compression")
        if self.format == "tfrecord" and self.compression not in tfrecord_compressions:
            raise ValueError("invalid tfrecord compression")
        return self

    def to_output_config(self) -> OutputConfig:
        if self.format == "parquet":
            return ParquetOutputConfig(compression=self.compression)  # type: ignore[arg-type]
        return TFRecordOutputConfig(
            compression=self.compression,  # type: ignore[arg-type]
            payload_encoding=self.payload_encoding,
            null_encoding=self.null_encoding,
        )

    @classmethod
    def from_output_config(cls, output: OutputConfig) -> "OutputSpec":
        if isinstance(output, ParquetOutputConfig):
            return cls(format="parquet", compression=output.compression)
        if isinstance(output, TFRecordOutputConfig):
            return cls(
                format="tfrecord",
                compression=output.compression,
                payload_encoding=output.payload_encoding,
                null_encoding=output.null_encoding,
            )
        raise TypeError("output must be a ParquetOutputConfig or TFRecordOutputConfig")


class ConversionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_spec: SchemaSpec = Field(
        default_factory=lambda: SchemaSpec(name="generic_conversion", version=1),
        alias="schema",
        serialization_alias="schema",
    )
    input: InputDiscoverySpec = Field(default_factory=InputDiscoverySpec)
    decoding: DecodingSpec = Field(default_factory=DecodingSpec)
    assembly: AssemblySpec | None = None
    features: dict[str, FeatureSpec] = Field(default_factory=dict)
    labels: LabelSpec | None = None
    split: SplitSpec | None = None
    validation: ValidationSpec = Field(default_factory=ValidationSpec)
    output: OutputSpec = Field(default_factory=OutputSpec)
    mapping: MappingTemplate | None = None
    resample: ResampleConfig | None = None
    write_manifest: bool = True

    @property
    def schema(self) -> SchemaSpec:
        return self.schema_spec

    @model_validator(mode="after")
    def _validate_feature_names(self) -> "ConversionSpec":
        for feature_name in self.features:
            if not isinstance(feature_name, str) or not feature_name.strip():
                raise ValueError("feature names must be non-empty")
        if self.labels is not None and self.labels.primary is not None:
            if not isinstance(self.labels.primary, str) or not self.labels.primary.strip():
                raise ValueError("label primary feature must be non-empty")
        return self

    @model_validator(mode="after")
    def _infer_join_defaults(self) -> "ConversionSpec":
        if self.assembly is None or not self.features:
            return self

        for join in self.assembly.joins:
            if join.default_value is not None:
                continue
            inferred_default = _build_topic_zero_default(join.topic, self.features)
            if inferred_default is not None:
                join.default_value = inferred_default
        return self

    def to_output_config(self) -> OutputConfig:
        return self.output.to_output_config()

    @property
    def uses_schema_aware_path(self) -> bool:
        return bool(
            self.features
            or self.assembly is not None
            or self.decoding.topics
            or self.labels is not None
            or self.split is not None
            or self.validation.preview
            or self.output.shards > 1
            or self.output.filename_template is not None
        )

    @classmethod
    def from_legacy(
        cls,
        *,
        mapping: MappingTemplate | Dict[str, List[str]],
        output: OutputConfig,
        resample: ResampleConfig | None = None,
        write_manifest: bool = True,
        schema_name: str = "legacy_mapping",
        schema_version: int = 1,
    ) -> "ConversionSpec":
        resolved_mapping = MappingTemplate.model_validate(mapping)
        include_topics = sorted(
            {
                source_topic
                for source_topics in resolved_mapping.root.values()
                for source_topic in source_topics
            }
        )
        return cls(
            schema_spec=SchemaSpec(name=schema_name, version=schema_version),
            input=InputDiscoverySpec(include_topics=include_topics),
            mapping=resolved_mapping,
            resample=resample,
            output=OutputSpec.from_output_config(output),
            write_manifest=write_manifest,
        )


def build_legacy_conversion_spec(
    *,
    mapping: MappingTemplate | Dict[str, List[str]],
    output: OutputConfig,
    resample: ResampleConfig | None = None,
    write_manifest: bool = True,
    schema_name: str = "legacy_mapping",
    schema_version: int = 1,
) -> ConversionSpec:
    return ConversionSpec.from_legacy(
        mapping=mapping,
        output=output,
        resample=resample,
        write_manifest=write_manifest,
        schema_name=schema_name,
        schema_version=schema_version,
    )


def _topic_to_feature_name(topic: str, used_names: set[str]) -> str:
    candidate = topic.strip("/")
    candidate = re.sub(r"[^a-zA-Z0-9]+", "_", candidate).strip("_").lower()
    if not candidate:
        candidate = "topic"

    feature_name = candidate
    suffix = 2
    while feature_name in used_names:
        feature_name = f"{candidate}_{suffix}"
        suffix += 1

    used_names.add(feature_name)
    return feature_name


def build_single_trigger_sensor_log_template(
    *,
    trigger_topic: str = "/trigger",
    join_topics: list[str] | None = None,
    schema_name: str = "single_trigger_sensor_log",
    schema_version: int = 1,
) -> ConversionSpec:
    normalized_trigger_topic = trigger_topic.strip()
    if not normalized_trigger_topic:
        raise ValueError("trigger_topic must be non-empty")

    normalized_join_topics = []
    for topic in join_topics or []:
        if not isinstance(topic, str):
            raise TypeError("join_topics must contain strings")
        stripped = topic.strip()
        if not stripped:
            raise ValueError("join_topics must contain non-empty values")
        normalized_join_topics.append(stripped)

    topics = [normalized_trigger_topic, *normalized_join_topics]
    used_feature_names: set[str] = set()
    features: dict[str, FeatureSpec] = {}

    for topic in topics:
        feature_name = _topic_to_feature_name(topic, used_feature_names)
        features[feature_name] = FeatureSpec(
            source=FieldSourceSpec(topic=topic),
            dtype="json",
        )

    return ConversionSpec(
        schema_spec=SchemaSpec(name=schema_name, version=schema_version),
        input=InputDiscoverySpec(include_topics=topics),
        assembly=AssemblySpec(
            trigger_topic=normalized_trigger_topic,
            joins=[
                JoinSpec(topic=topic, sync_policy="last-known-before", required=False)
                for topic in normalized_join_topics
            ],
        ),
        features=features,
        validation=ValidationSpec(
            sample_n=32,
            fail_fast=False,
            expected_features=list(features.keys()),
        ),
        output=OutputSpec(format="tfrecord"),
    )


def build_doom_ros_train_py_compatible() -> ConversionSpec:
    return ConversionSpec(
        schema_spec=SchemaSpec(name="doom_ros_train_py_compatible", version=1),
        input=InputDiscoverySpec(include_topics=["/doom_image", "/joy"]),
        decoding=DecodingSpec(
            topics={
                "/doom_image": TopicDecodeSpec(type_hint="custom_msgs/msg/RawImageBGRA"),
                "/joy": TopicDecodeSpec(type_hint="sensor_msgs/msg/Joy"),
            },
            on_decode_failure="warn",
        ),
        assembly=AssemblySpec(
            trigger_topic="/doom_image",
            joins=[
                JoinSpec(
                    topic="/joy",
                    sync_policy="last-known-before",
                    staleness_ns=250_000_000,
                    required=True,
                    default_value={"buttons": [0] * 15},
                )
            ],
        ),
        features={
            "image": FeatureSpec(
                source=FieldSourceSpec(topic="/doom_image", field_path="data"),
                dtype="bytes",
                required=True,
                transforms=[
                    TransformSpec(
                        kind="image_color_convert",
                        params={"from": "bgra", "to": "rgb"},
                    ),
                    TransformSpec(kind="image_encode", params={"format": "png"}),
                ],
            ),
            "buttons": FeatureSpec(
                source=FieldSourceSpec(topic="/joy", field_path="buttons"),
                dtype="int64",
                shape=[15],
                required=True,
                missing="zeros",
                transforms=[TransformSpec(kind="cast", params={"dtype": "int64"})],
            ),
        },
        labels=LabelSpec(primary="buttons"),
        validation=ValidationSpec(
            sample_n=128,
            fail_fast=True,
            bad_record_budget=0,
            expected_features=["image", "buttons"],
        ),
        output=OutputSpec(
            format="tfrecord",
            compression="gzip",
            shards=8,
            filename_template="{split}-{shard:05d}-of-{num_shards:05d}.tfrecord",
        ),
    )


class ParquetOutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["parquet"] = "parquet"
    compression: ParquetCompression = "none"


class TFRecordOutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["tfrecord"] = "tfrecord"
    compression: TFRecordCompression = "none"
    payload_encoding: TFRecordPayloadEncoding = "typed_features"
    null_encoding: TFRecordNullEncoding = "presence_flag"


OutputConfig: TypeAlias = Annotated[
    ParquetOutputConfig | TFRecordOutputConfig,
    Field(discriminator="format"),
]


class EpisodeRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    episode_id: str
    bag_path: str

    @field_validator("episode_id", "bag_path")
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("must be non-empty")
        return value


class MappingTemplate(RootModel[Dict[str, List[str]]]):
    @field_validator("root")
    @classmethod
    def _validate_mapping(cls, value: Dict[str, List[str]]) -> Dict[str, List[str]]:
        for target_field, source_topics in value.items():
            if not target_field:
                raise ValueError("mapping target field names must be non-empty")
            if not isinstance(source_topics, list):
                raise ValueError("mapping values must be lists of topic names")
            for source_topic in source_topics:
                if not source_topic:
                    raise ValueError("mapping source topic names must be non-empty")
        return value


class ReaderMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    ros_version: RosVersion
    storage_format: StorageFormat
    file_size_bytes: int = Field(ge=0)
    source_metadata: dict[str, Any] | None = None


class TemporalMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_timestamp: int | None = None
    end_timestamp: int | None = None
    start_time_iso: str | None = None
    end_time_iso: str | None = None
    duration_seconds: float = Field(ge=0)
    message_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_time_range(self) -> "TemporalMetadata":
        if self.start_timestamp is None and self.end_timestamp is None:
            return self
        if self.start_timestamp is None or self.end_timestamp is None:
            raise ValueError("start_timestamp and end_timestamp must both be set or both be None")
        if self.end_timestamp < self.start_timestamp:
            raise ValueError("end_timestamp must be greater than or equal to start_timestamp")
        return self


class Topic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    message_type: str = Field(min_length=1)
    message_count: int = Field(ge=0)
    rate_hz: float = Field(ge=0)


class BagMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    ros_version: RosVersion
    storage_format: StorageFormat
    file_size_bytes: int = Field(ge=0)
    start_timestamp: int | None = None
    end_timestamp: int | None = None
    start_time_iso: str | None = None
    end_time_iso: str | None = None
    duration_seconds: float = Field(ge=0)
    message_count: int = Field(ge=0)
    topics: list[Topic]
    compression_format: CompressionFormat


__all__ = [
    "CompressionFormat",
    "ParquetCompression",
    "ResampleMethod",
    "ResampleStrategy",
    "RosVersion",
    "StorageFormat",
    "TFRecordCompression",
    "TFRecordNullEncoding",
    "TFRecordPayloadEncoding",
    "SchemaSpec",
    "FieldSourceSpec",
    "InputDiscoverySpec",
    "DecodeFailurePolicy",
    "TopicDecodeSpec",
    "DecodingSpec",
    "SyncPolicy",
    "MissingDataPolicy",
    "FeatureDType",
    "JoinSpec",
    "AssemblySpec",
    "TransformSpec",
    "FeatureSpec",
    "LabelSpec",
    "SplitSpec",
    "ValidationSpec",
    "OutputSpec",
    "ConversionSpec",
    "build_legacy_conversion_spec",
    "build_single_trigger_sensor_log_template",
    "build_doom_ros_train_py_compatible",
    "Message",
    "ReaderMetadata",
    "InternalStats",
    "GroupingConfig",
    "ResampleConfig",
    "ParquetOutputConfig",
    "TFRecordOutputConfig",
    "OutputConfig",
    "EpisodeRef",
    "MappingTemplate",
    "TemporalMetadata",
    "Topic",
    "BagMetadata",
]
