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
    "ResampleMethod",
    "ResampleStrategy",
    "RosVersion",
    "StorageFormat",
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
