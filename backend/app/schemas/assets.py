"""Pydantic schemas for asset-related API requests and responses."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
