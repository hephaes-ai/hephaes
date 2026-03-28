from __future__ import annotations

import json
from uuid import uuid4

from .errors import WorkspaceError
from .models import WorkspaceJob
from .serialization import row_to_workspace_job, to_db_timestamp
from .utils import _utc_now


class WorkspaceJobMixin:
    def create_job(
        self,
        *,
        kind: str,
        target_asset_ids: list[str] | None = None,
        config: dict | None = None,
        job_id: str | None = None,
    ) -> WorkspaceJob:
        timestamp = _utc_now()
        job_id = job_id or str(uuid4())
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO jobs(
                    id,
                    kind,
                    status,
                    target_asset_ids_json,
                    config_json,
                    conversion_run_id,
                    error_message,
                    created_at,
                    updated_at,
                    started_at,
                    completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    kind,
                    "pending",
                    json.dumps(target_asset_ids or []),
                    json.dumps(config or {}),
                    None,
                    None,
                    to_db_timestamp(timestamp),
                    to_db_timestamp(timestamp),
                    None,
                    None,
                ),
            )
        return self.get_job_or_raise(job_id)

    def list_jobs(self) -> list[WorkspaceJob]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM jobs
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        return [row_to_workspace_job(row) for row in rows]

    def get_job(self, job_id: str) -> WorkspaceJob | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return row_to_workspace_job(row)

    def get_job_or_raise(self, job_id: str) -> WorkspaceJob:
        job = self.get_job(job_id)
        if job is None:
            raise WorkspaceError(f"job not found: {job_id}")
        return job

    def mark_job_running(self, job_id: str) -> WorkspaceJob:
        timestamp = _utc_now()
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'running', updated_at = ?, started_at = COALESCE(started_at, ?)
                WHERE id = ?
                """,
                (
                    to_db_timestamp(timestamp),
                    to_db_timestamp(timestamp),
                    job_id,
                ),
            )
        return self.get_job_or_raise(job_id)

    def mark_job_succeeded(
        self,
        job_id: str,
        *,
        conversion_run_id: str | None = None,
    ) -> WorkspaceJob:
        timestamp = _utc_now()
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'succeeded', conversion_run_id = COALESCE(?, conversion_run_id),
                    error_message = NULL, updated_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    conversion_run_id,
                    to_db_timestamp(timestamp),
                    to_db_timestamp(timestamp),
                    job_id,
                ),
            )
        return self.get_job_or_raise(job_id)

    def mark_job_failed(self, job_id: str, *, error_message: str) -> WorkspaceJob:
        timestamp = _utc_now()
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'failed', error_message = ?, updated_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    error_message,
                    to_db_timestamp(timestamp),
                    to_db_timestamp(timestamp),
                    job_id,
                ),
            )
        return self.get_job_or_raise(job_id)
