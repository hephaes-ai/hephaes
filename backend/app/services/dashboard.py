"""Service helpers for workspace-backed dashboard aggregation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job, utc_now
from app.schemas.dashboard import (
    DashboardBlockersResponse,
    DashboardConversionsSummary,
    DashboardCountEntry,
    DashboardFreshness,
    DashboardIndexingSummary,
    DashboardInventorySummary,
    DashboardJobsSummary,
    DashboardOutputsSummary,
    DashboardSummaryResponse,
    DashboardTrendBucket,
    DashboardTrendsResponse,
)
from hephaes import Workspace, WorkspaceJob
from hephaes._workspace_models import ConversionRun, OutputArtifact as WorkspaceOutputArtifact, RegisteredAsset

OUTPUT_AVAILABILITY_STATUSES = ("ready", "missing", "invalid")
ASSET_INDEXING_STATUSES = ("pending", "indexing", "indexed", "failed")
JOB_STATUSES = ("queued", "running", "succeeded", "failed")


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _start_of_day(value: datetime) -> datetime:
    normalized = _normalize_utc(value)
    return normalized.replace(hour=0, minute=0, second=0, microsecond=0)


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


def _status_counts(values: list[str], *, ordered_statuses: tuple[str, ...]) -> dict[str, int]:
    counts = {status: 0 for status in ordered_statuses}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _dynamic_count_entries(values: list[str]) -> list[DashboardCountEntry]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return _build_count_entries(counts)


def _windowed_trend(timestamps: list[datetime | None], *, now: datetime, days: int) -> list[DashboardTrendBucket]:
    start_day = _start_of_day(now) - timedelta(days=days - 1)
    end_day_exclusive = _start_of_day(now) + timedelta(days=1)
    counts_by_date: dict[str, int] = {}
    for timestamp in timestamps:
        if timestamp is None:
            continue
        normalized = _normalize_utc(timestamp)
        if normalized < start_day or normalized >= end_day_exclusive:
            continue
        date_key = normalized.date().isoformat()
        counts_by_date[date_key] = counts_by_date.get(date_key, 0) + 1

    return [
        DashboardTrendBucket(
            date=(start_day + timedelta(days=offset)).date().isoformat(),
            count=counts_by_date.get((start_day + timedelta(days=offset)).date().isoformat(), 0),
        )
        for offset in range(days)
    ]


def _count_where(items, predicate) -> int:
    return sum(1 for item in items if predicate(item))


def _sum_where(items, selector) -> int:
    return sum(int(selector(item) or 0) for item in items)


def _latest_timestamp(values: list[datetime | None]) -> datetime | None:
    filtered = [_normalize_utc(value) for value in values if value is not None]
    return max(filtered, default=None)


def _backend_visualization_jobs(session: Session) -> list[Job]:
    statement = (
        select(Job)
        .where(Job.type == "prepare_visualization")
        .order_by(Job.created_at.desc(), Job.id.desc())
    )
    return list(session.scalars(statement).all())


def _refresh_workspace_outputs(workspace: Workspace) -> list[WorkspaceOutputArtifact]:
    artifacts = [
        workspace.get_output_artifact_or_raise(summary.id)
        for summary in workspace.list_output_artifacts()
    ]
    artifacts_by_run_id: dict[str | None, list[WorkspaceOutputArtifact]] = {}
    for artifact in artifacts:
        artifacts_by_run_id.setdefault(artifact.conversion_run_id, []).append(artifact)

    refreshed_by_id: dict[str, WorkspaceOutputArtifact] = {}
    for conversion_run_id, grouped_artifacts in artifacts_by_run_id.items():
        if conversion_run_id is None:
            for artifact in grouped_artifacts:
                refreshed_by_id[artifact.id] = artifact
            continue

        run = workspace.get_conversion_run(conversion_run_id)
        if run is None:
            for artifact in grouped_artifacts:
                refreshed_by_id[artifact.id] = artifact
            continue

        representative = grouped_artifacts[0]
        workspace.register_output_artifacts(
            output_root=Path(run.output_dir),
            conversion_run_id=run.id,
            source_asset_id=representative.source_asset_id,
            source_asset_path=representative.source_asset_path,
            saved_config_id=representative.saved_config_id,
        )
        for artifact in grouped_artifacts:
            refreshed_by_id[artifact.id] = workspace.get_output_artifact_or_raise(artifact.id)

    return [refreshed_by_id[artifact.id] for artifact in artifacts]


def _job_status(job: WorkspaceJob | Job) -> str:
    if isinstance(job, WorkspaceJob):
        return "queued" if job.status == "pending" else job.status
    return job.status


def _job_failure_timestamp(job: WorkspaceJob | Job) -> datetime | None:
    if isinstance(job, WorkspaceJob):
        return job.completed_at or job.updated_at or job.created_at
    return job.finished_at or job.updated_at or job.created_at


def _job_updated_at(job: WorkspaceJob | Job) -> datetime | None:
    return job.updated_at


def _conversion_status(conversion: ConversionRun) -> str:
    return conversion.status


def _conversion_created_at(conversion: ConversionRun) -> datetime:
    return conversion.created_at


def _conversion_updated_at(conversion: ConversionRun) -> datetime:
    return conversion.updated_at


def _output_format(output: WorkspaceOutputArtifact) -> str:
    return output.format


def _output_availability(output: WorkspaceOutputArtifact) -> str:
    return output.availability_status


def _output_size(output: WorkspaceOutputArtifact) -> int:
    return int(output.size_bytes or 0)


def _output_created_at(output: WorkspaceOutputArtifact) -> datetime:
    return output.created_at


def _output_updated_at(output: WorkspaceOutputArtifact) -> datetime:
    return output.updated_at


def _asset_registration_at(asset: RegisteredAsset) -> datetime:
    return asset.registered_at


def _asset_last_indexed_at(asset: RegisteredAsset) -> datetime | None:
    return asset.last_indexed_at


def get_dashboard_summary(workspace: Workspace, session: Session) -> DashboardSummaryResponse:
    now = utc_now()
    assets = workspace.list_assets()
    jobs = [*workspace.list_jobs(), *_backend_visualization_jobs(session)]
    conversions = workspace.list_conversion_runs()
    outputs = _refresh_workspace_outputs(workspace)

    inventory = DashboardInventorySummary(
        asset_count=len(assets),
        total_asset_bytes=_sum_where(assets, lambda asset: asset.file_size),
        registered_last_24h=_count_where(
            assets,
            lambda asset: _normalize_utc(_asset_registration_at(asset)) >= now - timedelta(hours=24),
        ),
        registered_last_7d=_count_where(
            assets,
            lambda asset: _normalize_utc(_asset_registration_at(asset)) >= now - timedelta(days=7),
        ),
        registered_last_30d=_count_where(
            assets,
            lambda asset: _normalize_utc(_asset_registration_at(asset)) >= now - timedelta(days=30),
        ),
    )

    indexing = DashboardIndexingSummary(
        status_counts=_status_counts(
            [asset.indexing_status for asset in assets],
            ordered_statuses=ASSET_INDEXING_STATUSES,
        )
    )

    job_status_counts = _status_counts(
        [_job_status(job) for job in jobs],
        ordered_statuses=JOB_STATUSES,
    )
    jobs_summary = DashboardJobsSummary(
        active_count=job_status_counts["queued"] + job_status_counts["running"],
        failed_last_24h=_count_where(
            jobs,
            lambda job: _job_status(job) == "failed"
            and (_job_failure_timestamp(job) is not None)
            and _normalize_utc(_job_failure_timestamp(job)) >= now - timedelta(hours=24),
        ),
        status_counts=job_status_counts,
    )

    conversions_summary = DashboardConversionsSummary(
        status_counts=_status_counts(
            [_conversion_status(conversion) for conversion in conversions],
            ordered_statuses=JOB_STATUSES,
        )
    )

    output_availability_counts = _status_counts(
        [_output_availability(output) for output in outputs],
        ordered_statuses=OUTPUT_AVAILABILITY_STATUSES,
    )
    outputs_summary = DashboardOutputsSummary(
        output_count=len(outputs),
        total_output_bytes=_sum_where(outputs, _output_size),
        outputs_created_last_7d=_count_where(
            outputs,
            lambda output: _normalize_utc(_output_created_at(output)) >= now - timedelta(days=7),
        ),
        format_counts=_dynamic_count_entries([_output_format(output) for output in outputs]),
        availability_counts=_build_count_entries(
            output_availability_counts,
            preferred_order=OUTPUT_AVAILABILITY_STATUSES,
            include_zero=True,
        ),
    )

    freshness = DashboardFreshness(
        computed_at=now,
        latest_asset_registration_at=_latest_timestamp([_asset_registration_at(asset) for asset in assets]),
        latest_asset_indexed_at=_latest_timestamp([_asset_last_indexed_at(asset) for asset in assets]),
        latest_job_update_at=_latest_timestamp([_job_updated_at(job) for job in jobs]),
        latest_conversion_update_at=_latest_timestamp([_conversion_updated_at(conversion) for conversion in conversions]),
        latest_output_update_at=_latest_timestamp([_output_updated_at(output) for output in outputs]),
    )

    return DashboardSummaryResponse(
        inventory=inventory,
        indexing=indexing,
        jobs=jobs_summary,
        conversions=conversions_summary,
        outputs=outputs_summary,
        freshness=freshness,
    )


def get_dashboard_trends(workspace: Workspace, session: Session, *, days: int = 7) -> DashboardTrendsResponse:
    now = utc_now()
    assets = workspace.list_assets()
    jobs = [*workspace.list_jobs(), *_backend_visualization_jobs(session)]
    conversions = workspace.list_conversion_runs()
    outputs = _refresh_workspace_outputs(workspace)

    return DashboardTrendsResponse(
        days=days,
        registrations_by_day=_windowed_trend([_asset_registration_at(asset) for asset in assets], now=now, days=days),
        job_failures_by_day=_windowed_trend(
            [
                _job_failure_timestamp(job)
                for job in jobs
                if _job_status(job) == "failed"
            ],
            now=now,
            days=days,
        ),
        conversions_by_day=_windowed_trend(
            [_conversion_created_at(conversion) for conversion in conversions],
            now=now,
            days=days,
        ),
        conversion_failures_by_day=_windowed_trend(
            [
                _conversion_updated_at(conversion)
                for conversion in conversions
                if _conversion_status(conversion) == "failed"
            ],
            now=now,
            days=days,
        ),
        outputs_created_by_day=_windowed_trend(
            [_output_created_at(output) for output in outputs],
            now=now,
            days=days,
        ),
    )


def get_dashboard_blockers(workspace: Workspace, session: Session) -> DashboardBlockersResponse:
    assets = workspace.list_assets()
    jobs = [*workspace.list_jobs(), *_backend_visualization_jobs(session)]
    conversions = workspace.list_conversion_runs()
    outputs = _refresh_workspace_outputs(workspace)

    asset_status_counts = _status_counts(
        [asset.indexing_status for asset in assets],
        ordered_statuses=ASSET_INDEXING_STATUSES,
    )
    job_status_counts = _status_counts(
        [_job_status(job) for job in jobs],
        ordered_statuses=JOB_STATUSES,
    )
    conversion_status_counts = _status_counts(
        [_conversion_status(conversion) for conversion in conversions],
        ordered_statuses=JOB_STATUSES,
    )
    output_availability_counts = _status_counts(
        [_output_availability(output) for output in outputs],
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
