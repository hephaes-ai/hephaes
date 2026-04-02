"""Pydantic schemas for app-level workspace registry state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

WorkspaceStatus = Literal["ready", "missing", "invalid"]


class WorkspaceRegistrySummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    active_job_count: int = Field(ge=0, default=0)
    root_path: str = Field(min_length=1)
    workspace_dir: str = Field(min_length=1)
    database_path: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime | None = None
    status: WorkspaceStatus
    status_reason: str | None = None

    @field_validator("created_at", "updated_at", "last_opened_at", mode="before")
    @classmethod
    def normalize_datetimes_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)


class WorkspaceRegistryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_workspace_id: str | None = None
    workspaces: list[WorkspaceRegistrySummaryResponse]


class WorkspaceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_path: str = Field(min_length=1)
    name: str | None = None
    activate: bool = True

    @field_validator("root_path")
    @classmethod
    def validate_root_path(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("root_path must be non-empty")
        return stripped

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
