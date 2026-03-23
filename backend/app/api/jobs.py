"""Job routes for durable backend job tracking."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.jobs import JobResponse
from app.services.jobs import JobNotFoundError, get_job_or_raise, list_jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])
DbSession = Annotated[Session, Depends(get_db_session)]


def _build_job_response(job) -> JobResponse:
    payload = JobResponse.model_validate(job).model_dump()
    config_payload = payload.get("config_json")
    if isinstance(config_payload, dict):
        payload["representation_policy"] = config_payload.get("representation_policy")
    return JobResponse.model_validate(payload)


@router.get("", response_model=list[JobResponse])
def list_jobs_route(session: DbSession) -> list[JobResponse]:
    return [_build_job_response(job) for job in list_jobs(session)]


@router.get("/{job_id}", response_model=JobResponse)
def get_job_route(job_id: str, session: DbSession) -> JobResponse:
    try:
        job = get_job_or_raise(session, job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _build_job_response(job)
