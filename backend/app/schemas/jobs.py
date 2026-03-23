"""Pydantic schemas for durable job tracking responses."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

JobType = Literal["index", "convert", "prepare_visualization"]
JobStatus = Literal["queued", "running", "succeeded", "failed"]


class JobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str = Field(min_length=1)
    type: JobType
    status: JobStatus
    target_asset_ids_json: list[str] = Field(default_factory=list)
    config_json: dict[str, Any] = Field(default_factory=dict)
    representation_policy: dict[str, Any] | None = None
    output_path: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @field_validator("created_at", "updated_at", "started_at", "finished_at", mode="before")
    @classmethod
    def normalize_datetimes_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)
