"""Service helpers for dashboard summary and trend aggregation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    ASSET_INDEXING_STATUSES,
    JOB_STATUSES,
    Asset,
    Conversion,
    Job,
    OutputArtifact,
    utc_now,
)
from app.schemas.dashboard import (
    DashboardBlockersResponse,
    DashboardCountEntry,
    DashboardConversionsSummary,
    DashboardFreshness,
    DashboardIndexingSummary,
    DashboardInventorySummary,
    DashboardJobsSummary,
    DashboardOutputsSummary,
    DashboardSummaryResponse,
    DashboardTrendBucket,
    DashboardTrendsResponse,
)
from app.services.outputs import backfill_output_artifacts

OUTPUT_AVAILABILITY_STATUSES = ("ready", "missing", "invalid")


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _start_of_day(value: datetime) -> datetime:
    normalized = _normalize_utc(value)
    return normalized.replace(hour=0, minute=0, second=0, microsecond=0)


def _count_rows(session: Session, model: Any, *filters: Any) -> int:
    statement = select(func.count()).select_from(model)
    if filters:
        statement = statement.where(*filters)
    return int(session.scalar(statement) or 0)


def _sum_int(session: Session, model: Any, column: Any, *filters: Any) -> int:
    statement = select(func.coalesce(func.sum(column), 0)).select_from(model)
    if filters:
        statement = statement.where(*filters)
    return int(session.scalar(statement) or 0)


def _max_timestamp(session: Session, model: Any, column: Any, *filters: Any) -> datetime | None:
    statement = select(func.max(column)).select_from(model)
    if filters:
        statement = statement.where(*filters)
    return session.scalar(statement)


def _status_counts(
    session: Session,
    *,
    model: Any,
    column: Any,
    ordered_statuses: tuple[str, ...],
    filters: tuple[Any, ...] = (),
) -> dict[str, int]:
    statement = select(column, func.count()).select_from(model)
    if filters:
        statement = statement.where(*filters)
    statement = statement.group_by(column)

    counts = {status: 0 for status in ordered_statuses}
    for key, count in session.execute(statement).all():
        if key is None:
            continue
        counts[str(key)] = int(count or 0)
    return counts


def _build_count_entries(
    counts: dict[str, int],
    *,
    preferred_order: tuple[str, ...] = (),
    include_zero: bool = False,
) -> list[DashboardCountEntry]:
    entries: list[DashboardCountEntry] = []
    seen: set[str] = set()

    for key in preferred_order:
        seen.add(key)
        count = int(counts.get(key, 0))
        if include_zero or count > 0:
            entries.append(DashboardCountEntry(key=key, count=count))

    extras = [
        DashboardCountEntry(key=key, count=int(count))
        for key, count in counts.items()
        if key not in seen and (include_zero or int(count) > 0)
    ]
    extras.sort(key=lambda entry: (-entry.count, entry.key))
    return entries + extras


def _dynamic_count_entries(
    session: Session,
    *,
    model: Any,
    column: Any,
    filters: tuple[Any, ...] = (),
) -> list[DashboardCountEntry]:
    statement = select(column, func.count()).select_from(model)
    if filters:
        statement = statement.where(*filters)
    statement = statement.group_by(column)

    counts: dict[str, int] = {}
    for key, count in session.execute(statement).all():
        if key is None:
            continue
        counts[str(key)] = int(count or 0)

    return _build_count_entries(counts)


def _windowed_trend(
    session: Session,
    *,
    model: Any,
    column: Any,
    now: datetime,
    days: int,
    filters: tuple[Any, ...] = (),
) -> list[DashboardTrendBucket]:
    start_day = _start_of_day(now) - timedelta(days=days - 1)
    end_day_exclusive = _start_of_day(now) + timedelta(days=1)
    day_expression = func.date(column)

    statement = (
        select(day_expression, func.count())
        .select_from(model)
        .where(column >= start_day, column < end_day_exclusive, *filters)
        .group_by(day_expression)
    )
    counts_by_date = {
        str(day_key): int(count or 0)
        for day_key, count in session.execute(statement).all()
        if day_key is not None
    }

    return [
        DashboardTrendBucket(
            date=(start_day + timedelta(days=offset)).date().isoformat(),
            count=counts_by_date.get((start_day + timedelta(days=offset)).date().isoformat(), 0),
        )
        for offset in range(days)
    ]


def get_dashboard_summary(session: Session) -> DashboardSummaryResponse:
    backfill_output_artifacts(session)
    now = utc_now()

    inventory = DashboardInventorySummary(
        asset_count=_count_rows(session, Asset),
        total_asset_bytes=_sum_int(session, Asset, Asset.file_size),
        registered_last_24h=_count_rows(session, Asset, Asset.registered_time >= now - timedelta(hours=24)),
        registered_last_7d=_count_rows(session, Asset, Asset.registered_time >= now - timedelta(days=7)),
        registered_last_30d=_count_rows(session, Asset, Asset.registered_time >= now - timedelta(days=30)),
    )

    indexing_status_counts = _status_counts(
        session,
        model=Asset,
        column=Asset.indexing_status,
        ordered_statuses=ASSET_INDEXING_STATUSES,
    )
    indexing = DashboardIndexingSummary(status_counts=indexing_status_counts)

    job_status_counts = _status_counts(
        session,
        model=Job,
        column=Job.status,
        ordered_statuses=JOB_STATUSES,
    )
    job_failure_timestamp = func.coalesce(Job.finished_at, Job.updated_at, Job.created_at)
    jobs = DashboardJobsSummary(
        active_count=job_status_counts["queued"] + job_status_counts["running"],
        failed_last_24h=_count_rows(
            session,
            Job,
            Job.status == "failed",
            job_failure_timestamp >= now - timedelta(hours=24),
        ),
        status_counts=job_status_counts,
    )

    conversion_status_counts = _status_counts(
        session,
        model=Conversion,
        column=Conversion.status,
        ordered_statuses=JOB_STATUSES,
    )
    conversions = DashboardConversionsSummary(status_counts=conversion_status_counts)

    output_availability_counts = _status_counts(
        session,
        model=OutputArtifact,
        column=OutputArtifact.availability_status,
        ordered_statuses=OUTPUT_AVAILABILITY_STATUSES,
    )
    outputs = DashboardOutputsSummary(
        output_count=_count_rows(session, OutputArtifact),
        total_output_bytes=_sum_int(session, OutputArtifact, OutputArtifact.size_bytes),
        outputs_created_last_7d=_count_rows(
            session,
            OutputArtifact,
            OutputArtifact.created_at >= now - timedelta(days=7),
        ),
        format_counts=_dynamic_count_entries(
            session,
            model=OutputArtifact,
            column=OutputArtifact.format,
        ),
        availability_counts=_build_count_entries(
            output_availability_counts,
            preferred_order=OUTPUT_AVAILABILITY_STATUSES,
            include_zero=True,
        ),
    )

    freshness = DashboardFreshness(
        computed_at=now,
        latest_asset_registration_at=_max_timestamp(session, Asset, Asset.registered_time),
        latest_asset_indexed_at=_max_timestamp(session, Asset, Asset.last_indexed_time),
        latest_job_update_at=_max_timestamp(session, Job, Job.updated_at),
        latest_conversion_update_at=_max_timestamp(session, Conversion, Conversion.updated_at),
        latest_output_update_at=_max_timestamp(session, OutputArtifact, OutputArtifact.updated_at),
    )

    return DashboardSummaryResponse(
        inventory=inventory,
        indexing=indexing,
        jobs=jobs,
        conversions=conversions,
        outputs=outputs,
        freshness=freshness,
    )


def get_dashboard_trends(session: Session, *, days: int = 7) -> DashboardTrendsResponse:
    backfill_output_artifacts(session)
    now = utc_now()
    job_failure_timestamp = func.coalesce(Job.finished_at, Job.updated_at, Job.created_at)
    conversion_failure_timestamp = func.coalesce(Conversion.updated_at, Conversion.created_at)

    return DashboardTrendsResponse(
        days=days,
        registrations_by_day=_windowed_trend(
            session,
            model=Asset,
            column=Asset.registered_time,
            now=now,
            days=days,
        ),
        job_failures_by_day=_windowed_trend(
            session,
            model=Job,
            column=job_failure_timestamp,
            now=now,
            days=days,
            filters=(Job.status == "failed",),
        ),
        conversions_by_day=_windowed_trend(
            session,
            model=Conversion,
            column=Conversion.created_at,
            now=now,
            days=days,
        ),
        conversion_failures_by_day=_windowed_trend(
            session,
            model=Conversion,
            column=conversion_failure_timestamp,
            now=now,
            days=days,
            filters=(Conversion.status == "failed",),
        ),
        outputs_created_by_day=_windowed_trend(
            session,
            model=OutputArtifact,
            column=OutputArtifact.created_at,
            now=now,
            days=days,
        ),
    )


def get_dashboard_blockers(session: Session) -> DashboardBlockersResponse:
    backfill_output_artifacts(session)

    asset_status_counts = _status_counts(
        session,
        model=Asset,
        column=Asset.indexing_status,
        ordered_statuses=ASSET_INDEXING_STATUSES,
    )
    job_status_counts = _status_counts(
        session,
        model=Job,
        column=Job.status,
        ordered_statuses=JOB_STATUSES,
    )
    conversion_status_counts = _status_counts(
        session,
        model=Conversion,
        column=Conversion.status,
        ordered_statuses=JOB_STATUSES,
    )
    output_availability_counts = _status_counts(
        session,
        model=OutputArtifact,
        column=OutputArtifact.availability_status,
        ordered_statuses=OUTPUT_AVAILABILITY_STATUSES,
    )

    return DashboardBlockersResponse(
        pending_assets=asset_status_counts["pending"],
        failed_assets=asset_status_counts["failed"],
        failed_jobs=job_status_counts["failed"],
        failed_conversions=conversion_status_counts["failed"],
        missing_outputs=output_availability_counts["missing"],
        invalid_outputs=output_availability_counts["invalid"],
    )
