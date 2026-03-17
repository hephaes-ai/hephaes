"""Job routes for durable backend job tracking."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db_session
from backend.app.schemas.jobs import JobResponse
from backend.app.services.jobs import JobNotFoundError, get_job_or_raise, list_jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])
DbSession = Annotated[Session, Depends(get_db_session)]


@router.get("", response_model=list[JobResponse])
def list_jobs_route(session: DbSession) -> list[JobResponse]:
    return [JobResponse.model_validate(job) for job in list_jobs(session)]


@router.get("/{job_id}", response_model=JobResponse)
def get_job_route(job_id: str, session: DbSession) -> JobResponse:
    try:
        job = get_job_or_raise(session, job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return JobResponse.model_validate(job)
