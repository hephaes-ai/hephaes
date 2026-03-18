"""Pydantic schemas for visualization preparation and viewer-source manifests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.jobs import JobResponse

SourceKind = Literal["rrd_url", "grpc_url"]
ViewerSourceStatus = Literal["none", "preparing", "ready", "failed"]


class PrepareVisualizationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job: JobResponse


class ViewerSourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    episode_id: str = Field(min_length=1)
    status: ViewerSourceStatus
    source_kind: SourceKind | None = None
    source_url: str | None = None
    job_id: str | None = None
    artifact_path: str | None = None
    error_message: str | None = None
    viewer_version: str | None = None
    recording_version: str | None = None
    updated_at: datetime | None = None

    @field_validator("updated_at", mode="before")
    @classmethod
    def normalize_datetimes_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)
