from typing import Any, Dict, List, Literal, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

CompressionFormat = Literal["zstd", "lz4", "bz2", "none", "unknown"]
RosVersion = Literal["ROS1", "ROS2"]
StorageFormat = Literal["bag", "mcap", "unknown"]


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


class ParquetRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    episode_id: str = Field(min_length=1)
    bag_path: str = Field(min_length=1)
    ros_version: RosVersion
    message_index: int = Field(ge=0)
    timestamp_ns: int = Field(ge=0)
    topic: str = Field(min_length=1)
    field: str = Field(min_length=1)
    topic_type: str = Field(min_length=1)
    data_json: str

    @classmethod
    def column_names(cls) -> list[str]:
        return list(cls.model_fields.keys())

    @classmethod
    def parquet_schema_spec(cls) -> list[tuple[str, str]]:
        return [
            (name, _annotation_to_parquet_type(field.annotation))
            for name, field in cls.model_fields.items()
        ]


def _annotation_to_parquet_type(annotation: Any) -> str:
    if annotation is int:
        return "int64"
    if annotation is str:
        return "string"

    origin = get_origin(annotation)
    if origin is Literal:
        literal_values = get_args(annotation)
        if literal_values and all(isinstance(value, str) for value in literal_values):
            return "string"
        if literal_values and all(isinstance(value, int) for value in literal_values):
            return "int64"

    raise TypeError(f"Unsupported parquet annotation: {annotation!r}")


__all__ = [
    "CompressionFormat",
    "RosVersion",
    "StorageFormat",
    "Message",
    "ReaderMetadata",
    "InternalStats",
    "GroupingConfig",
    "EpisodeRef",
    "MappingTemplate",
    "TemporalMetadata",
    "Topic",
    "BagMetadata",
    "ParquetRow",
]
