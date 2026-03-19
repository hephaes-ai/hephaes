"""Pydantic schemas for episode playback and scrubber APIs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.assets import TopicModality

EpisodeSampleSelectionStrategy = Literal["latest_at_or_before", "window"]


class EpisodeStreamResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    stream_key: str = Field(min_length=1)
    source_topic: str = Field(min_length=1)
    message_type: str = Field(min_length=1)
    modality: TopicModality
    message_count: int = Field(ge=0)
    rate_hz: float = Field(ge=0)
    first_timestamp_ns: int | None = Field(default=None, ge=0)
    last_timestamp_ns: int | None = Field(default=None, ge=0)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class EpisodeDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    episode_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    source_kind: Literal["indexed_metadata"] = "indexed_metadata"
    start_time: datetime | None = None
    end_time: datetime | None = None
    start_timestamp_ns: int | None = Field(default=None, ge=0)
    end_timestamp_ns: int | None = Field(default=None, ge=0)
    duration_seconds: float = Field(ge=0)
    has_visualizable_streams: bool
    default_lane_count: int = Field(ge=0)
    stream_count: int = Field(ge=0)
    streams: list[EpisodeStreamResponse] = Field(default_factory=list)

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def normalize_datetimes_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)


class EpisodeTimelineBucketResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket_index: int = Field(ge=0)
    start_offset_ns: int = Field(ge=0)
    end_offset_ns: int = Field(ge=0)
    event_count: int = Field(ge=0)


class EpisodeTimelineLaneResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stream_id: str = Field(min_length=1)
    stream_key: str = Field(min_length=1)
    source_topic: str = Field(min_length=1)
    modality: TopicModality
    message_count: int = Field(ge=0)
    first_timestamp_ns: int | None = Field(default=None, ge=0)
    last_timestamp_ns: int | None = Field(default=None, ge=0)
    non_empty_bucket_count: int = Field(ge=0)
    buckets: list[EpisodeTimelineBucketResponse] = Field(default_factory=list)


class EpisodeTimelineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    episode_id: str = Field(min_length=1)
    start_timestamp_ns: int | None = Field(default=None, ge=0)
    end_timestamp_ns: int | None = Field(default=None, ge=0)
    duration_ns: int = Field(ge=0)
    bucket_count: int = Field(ge=1)
    lanes: list[EpisodeTimelineLaneResponse] = Field(default_factory=list)


class EpisodeSampleDataResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp_ns: int = Field(ge=0)
    payload: Any
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class EpisodeStreamSamplesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stream_id: str = Field(min_length=1)
    stream_key: str = Field(min_length=1)
    source_topic: str = Field(min_length=1)
    modality: TopicModality
    selection_strategy: EpisodeSampleSelectionStrategy
    sample_count: int = Field(ge=0)
    samples: list[EpisodeSampleDataResponse] = Field(default_factory=list)


class EpisodeSamplesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    episode_id: str = Field(min_length=1)
    requested_timestamp_ns: int = Field(ge=0)
    window_before_ns: int = Field(ge=0)
    window_after_ns: int = Field(ge=0)
    window_start_ns: int = Field(ge=0)
    window_end_ns: int = Field(ge=0)
    streams: list[EpisodeStreamSamplesResponse] = Field(default_factory=list)
