"""Pydantic schemas for asset-related API requests and responses."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

IndexingStatus = Literal["pending", "indexing", "indexed", "failed"]
TopicModality = Literal["image", "points", "scalar_series", "other"]
RegistrationSkipReason = Literal["duplicate", "invalid_path"]


class AssetRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(min_length=1)

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("file_path must be non-empty")
        return stripped


class AssetListQueryParams(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    search: str | None = None
    tag: str | None = None
    file_type: str | None = Field(default=None, alias="type")
    status: IndexingStatus | None = None
    min_duration: float | None = Field(default=None, ge=0)
    max_duration: float | None = Field(default=None, ge=0)
    start_after: datetime | None = None
    start_before: datetime | None = None

    @field_validator(
        "search",
        "tag",
        "file_type",
        "status",
        "min_duration",
        "max_duration",
        "start_after",
        "start_before",
        mode="before",
    )
    @classmethod
    def normalize_empty_values(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        stripped = value.strip()
        if not stripped:
            return None
        return stripped

    @field_validator("tag", mode="after")
    @classmethod
    def normalize_tag(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.lower()

    @field_validator("file_type", mode="after")
    @classmethod
    def normalize_file_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.lower()

    @field_validator("start_after", "start_before", mode="after")
    @classmethod
    def normalize_datetimes_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_ranges(self) -> "AssetListQueryParams":
        if (
            self.min_duration is not None
            and self.max_duration is not None
            and self.min_duration > self.max_duration
        ):
            raise ValueError("min_duration must be less than or equal to max_duration")

        if (
            self.start_after is not None
            and self.start_before is not None
            and self.start_after > self.start_before
        ):
            raise ValueError("start_after must be less than or equal to start_before")

        return self


class AssetSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    file_type: str = Field(min_length=1)
    file_size: int = Field(ge=0)
    registered_time: datetime
    indexing_status: IndexingStatus
    last_indexed_time: datetime | None = None

    @field_validator("registered_time", "last_indexed_time", mode="before")
    @classmethod
    def normalize_datetimes_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)


class AssetListItem(AssetSummary):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AssetRegistrationResponse(AssetSummary):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class TagCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must be non-empty")
        return stripped


class AssetTagAttachRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag_id: str = Field(min_length=1)

    @field_validator("tag_id")
    @classmethod
    def validate_tag_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("tag_id must be non-empty")
        return stripped


class TagResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def normalize_created_at_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)


class IndexedTopicSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_count: int = Field(ge=0)
    message_type: str = Field(min_length=1)
    modality: TopicModality
    name: str = Field(min_length=1)
    rate_hz: float = Field(ge=0)


class DefaultEpisodeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration: float = Field(ge=0)
    episode_id: str = Field(min_length=1)
    label: str = Field(min_length=1)


class VisualizationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_lane_count: int = Field(ge=0)
    has_visualizable_streams: bool


class AssetMetadataResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_episode: DefaultEpisodeSummary | None = None
    duration: float | None = Field(default=None, ge=0)
    end_time: datetime | None = None
    indexing_error: str | None = None
    message_count: int = Field(ge=0)
    raw_metadata: dict[str, Any]
    sensor_types: list[str]
    start_time: datetime | None = None
    topic_count: int = Field(ge=0)
    topics: list[IndexedTopicSummary]
    visualization_summary: VisualizationSummary | None = None

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def normalize_datetimes_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)


class AssetRegistrationSkip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    reason: RegistrationSkipReason


class DialogAssetRegistrationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canceled: bool
    registered_assets: list[AssetRegistrationResponse]
    skipped: list[AssetRegistrationSkip]


class ReindexAllResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    failed_assets: list[AssetSummary]
    indexed_assets: list[AssetSummary]
    total_requested: int = Field(ge=0)


class AssetDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: AssetSummary
    metadata: AssetMetadataResponse | None = None
    tags: list[TagResponse] = Field(default_factory=list)
