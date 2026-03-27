"""Service helpers for durable job tracking."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job, utc_now
from hephaes import WorkspaceJob


class JobServiceError(Exception):
    """Base exception for job service failures."""


class JobNotFoundError(JobServiceError):
    """Raised when a requested job cannot be found."""


class JobStateTransitionError(JobServiceError):
    """Raised when a job is moved through an invalid state transition."""


def list_jobs(session: Session) -> list[Job]:
    statement = select(Job).order_by(Job.created_at.desc(), Job.id.desc())
    return list(session.scalars(statement).all())


def get_job(session: Session, job_id: str) -> Job | None:
    return session.scalar(select(Job).where(Job.id == job_id))


def get_job_or_raise(session: Session, job_id: str) -> Job:
    job = get_job(session, job_id)
    if job is None:
        raise JobNotFoundError(f"job not found: {job_id}")
    return job


def find_latest_job_for_target(
    session: Session,
    *,
    job_type: str,
    target_asset_id: str,
    episode_id: str | None = None,
) -> Job | None:
    """Return the most recent job matching type, target asset, and optional episode."""
    statement = (
        select(Job)
        .where(Job.type == job_type)
        .order_by(Job.created_at.desc())
    )
    for job in session.scalars(statement).all():
        if target_asset_id not in (job.target_asset_ids_json or []):
            continue
        if episode_id is not None:
            config = job.config_json or {}
            if config.get("episode_id") != episode_id:
                continue
        return job
    return None


def sync_workspace_job(
    session: Session,
    *,
    job: WorkspaceJob,
    output_path: str | None = None,
) -> Job:
    db_job = session.get(Job, job.id)
    if db_job is None:
        db_job = Job(id=job.id)
        session.add(db_job)

    db_job.type = "index" if job.kind == "index_asset" else job.kind
    db_job.status = "queued" if job.status == "pending" else job.status
    db_job.target_asset_ids_json = list(job.target_asset_ids)
    config_json = dict(job.config)
    config_json.pop("max_workers", None)
    db_job.config_json = config_json
    db_job.output_path = output_path or config_json.get("output_path")
    db_job.error_message = job.error_message
    db_job.created_at = job.created_at
    db_job.updated_at = job.updated_at
    db_job.started_at = job.started_at
    db_job.finished_at = job.completed_at
    session.commit()
    session.refresh(db_job)
    return db_job


class JobService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_job(
        self,
        *,
        job_type: str,
        target_asset_ids: list[str] | None = None,
        config: dict[str, Any] | None = None,
        output_path: str | None = None,
    ) -> Job:
        job = Job(
            type=job_type,
            status="queued",
            target_asset_ids_json=list(target_asset_ids or []),
            config_json=dict(config or {}),
            output_path=output_path,
            error_message=None,
            started_at=None,
            finished_at=None,
        )
        self.session.add(job)
        self.session.commit()
        return get_job_or_raise(self.session, job.id)

    def mark_job_running(self, job_id: str) -> Job:
        job = get_job_or_raise(self.session, job_id)
        if job.status not in {"queued", "running"}:
            raise JobStateTransitionError(
                f"job cannot transition to running from {job.status}: {job.id}"
            )

        job.status = "running"
        if job.started_at is None:
            job.started_at = utc_now()
        job.finished_at = None
        job.error_message = None
        job.updated_at = utc_now()
        self.session.commit()
        return get_job_or_raise(self.session, job.id)

    def mark_job_succeeded(self, job_id: str, *, output_path: str | None = None) -> Job:
        job = get_job_or_raise(self.session, job_id)
        if job.status not in {"queued", "running", "succeeded"}:
            raise JobStateTransitionError(
                f"job cannot transition to succeeded from {job.status}: {job.id}"
            )

        if job.started_at is None:
            job.started_at = utc_now()
        job.status = "succeeded"
        if output_path is not None:
            job.output_path = output_path
        job.error_message = None
        job.finished_at = utc_now()
        job.updated_at = utc_now()
        self.session.commit()
        return get_job_or_raise(self.session, job.id)

    def mark_job_failed(self, job_id: str, *, error_message: str) -> Job:
        job = get_job_or_raise(self.session, job_id)
        if job.status not in {"queued", "running", "failed"}:
            raise JobStateTransitionError(
                f"job cannot transition to failed from {job.status}: {job.id}"
            )

        if job.started_at is None:
            job.started_at = utc_now()
        job.status = "failed"
        job.error_message = error_message
        job.finished_at = utc_now()
        job.updated_at = utc_now()
        self.session.commit()
        return get_job_or_raise(self.session, job.id)
