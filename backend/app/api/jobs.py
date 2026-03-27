"""Job routes for durable backend job tracking."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db_session, get_workspace
from app.mappers.workspace import map_job_response
from app.schemas.jobs import JobResponse
from app.services.jobs import JobNotFoundError, get_job_or_raise, list_jobs
from hephaes import Workspace

router = APIRouter(prefix="/jobs", tags=["jobs"])
WorkspaceDep = Annotated[Workspace, Depends(get_workspace)]
DbSession = Annotated[Session, Depends(get_db_session)]


@router.get("", response_model=list[JobResponse])
def list_jobs_route(workspace: WorkspaceDep, session: DbSession) -> list[JobResponse]:
    responses = {job.id: map_job_response(job) for job in workspace.list_jobs()}
    for job in list_jobs(session):
        payload = JobResponse.model_validate(job).model_dump()
        config_payload = payload.get("config_json")
        if isinstance(config_payload, dict):
            payload["representation_policy"] = config_payload.get("representation_policy")
        responses.setdefault(job.id, JobResponse.model_validate(payload))
    return sorted(
        responses.values(),
        key=lambda job: (job.created_at, job.id),
        reverse=True,
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job_route(job_id: str, workspace: WorkspaceDep, session: DbSession) -> JobResponse:
    job = workspace.get_job(job_id)
    if job is not None:
        return map_job_response(job)
    try:
        orm_job = get_job_or_raise(session, job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    payload = JobResponse.model_validate(orm_job).model_dump()
    config_payload = payload.get("config_json")
    if isinstance(config_payload, dict):
        payload["representation_policy"] = config_payload.get("representation_policy")
    return JobResponse.model_validate(payload)
