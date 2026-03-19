"""Pydantic schemas for output artifact catalog responses."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

OutputActionStatus = Literal["queued", "running", "succeeded", "failed"]


class OutputListQueryParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search: str | None = None
    format: str | None = None
    role: str | None = None
    asset_id: str | None = None
    conversion_id: str | None = None
    availability: str | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)

    @field_validator(
        "search",
        "format",
        "role",
        "asset_id",
        "conversion_id",
        "availability",
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

    @field_validator("format", "role", "availability", mode="after")
    @classmethod
    def normalize_lowercase_values(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.lower()


class OutputActionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("action_type")
    @classmethod
    def normalize_action_type(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("action_type must be non-empty")
        return stripped


class OutputActionSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    output_id: str = Field(min_length=1)
    action_type: str = Field(min_length=1)
    status: OutputActionStatus
    config: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    output_path: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @field_validator("created_at", "updated_at", "started_at", "finished_at", mode="before")
    @classmethod
    def normalize_action_datetimes_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)


class OutputActionDetailResponse(OutputActionSummaryResponse):
    model_config = ConfigDict(extra="forbid")

    output_file_path: str | None = None


class OutputArtifactSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    conversion_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    asset_ids: list[str] = Field(default_factory=list)
    relative_path: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    format: str = Field(min_length=1)
    role: str = Field(min_length=1)
    media_type: str | None = None
    size_bytes: int = Field(ge=0)
    availability_status: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    latest_action: OutputActionSummaryResponse | None = None
    content_url: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def normalize_datetimes_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)


class OutputArtifactDetailResponse(OutputArtifactSummaryResponse):
    model_config = ConfigDict(extra="forbid")

    file_path: str | None = None
