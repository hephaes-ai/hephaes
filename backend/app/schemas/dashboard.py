"""Pydantic schemas for dashboard summary endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.assets import IndexingStatus
from app.schemas.conversions import ConversionStatus
from app.schemas.jobs import JobStatus


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


class DashboardCountEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)
    count: int = Field(ge=0)


class DashboardTrendBucket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    count: int = Field(ge=0)


class DashboardInventorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_count: int = Field(ge=0)
    total_asset_bytes: int = Field(ge=0)
    registered_last_24h: int = Field(ge=0)
    registered_last_7d: int = Field(ge=0)
    registered_last_30d: int = Field(ge=0)


class DashboardIndexingSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status_counts: dict[IndexingStatus, int] = Field(default_factory=dict)


class DashboardJobsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_count: int = Field(ge=0)
    failed_last_24h: int = Field(ge=0)
    status_counts: dict[JobStatus, int] = Field(default_factory=dict)


class DashboardConversionsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status_counts: dict[ConversionStatus, int] = Field(default_factory=dict)


class DashboardOutputsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_count: int = Field(ge=0)
    total_output_bytes: int = Field(ge=0)
    outputs_created_last_7d: int = Field(ge=0)
    format_counts: list[DashboardCountEntry] = Field(default_factory=list)
    availability_counts: list[DashboardCountEntry] = Field(default_factory=list)


class DashboardFreshness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    computed_at: datetime
    latest_asset_registration_at: datetime | None = None
    latest_asset_indexed_at: datetime | None = None
    latest_job_update_at: datetime | None = None
    latest_conversion_update_at: datetime | None = None
    latest_output_update_at: datetime | None = None

    @field_validator(
        "computed_at",
        "latest_asset_registration_at",
        "latest_asset_indexed_at",
        "latest_job_update_at",
        "latest_conversion_update_at",
        "latest_output_update_at",
        mode="before",
    )
    @classmethod
    def normalize_datetimes_to_utc(cls, value: datetime | None) -> datetime | None:
        return _normalize_datetime(value)


class DashboardSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory: DashboardInventorySummary
    indexing: DashboardIndexingSummary
    jobs: DashboardJobsSummary
    conversions: DashboardConversionsSummary
    outputs: DashboardOutputsSummary
    freshness: DashboardFreshness


class DashboardTrendsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days: int = Field(ge=1, le=90)
    registrations_by_day: list[DashboardTrendBucket] = Field(default_factory=list)
    job_failures_by_day: list[DashboardTrendBucket] = Field(default_factory=list)
    conversions_by_day: list[DashboardTrendBucket] = Field(default_factory=list)
    conversion_failures_by_day: list[DashboardTrendBucket] = Field(default_factory=list)
    outputs_created_by_day: list[DashboardTrendBucket] = Field(default_factory=list)


class DashboardBlockersResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pending_assets: int = Field(ge=0)
    failed_assets: int = Field(ge=0)
    failed_jobs: int = Field(ge=0)
    failed_conversions: int = Field(ge=0)
    missing_outputs: int = Field(ge=0)
    invalid_outputs: int = Field(ge=0)
