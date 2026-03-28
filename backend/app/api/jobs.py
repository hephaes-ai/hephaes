"""Job routes for durable backend job tracking."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_workspace
from app.mappers.workspace import map_job_response
from app.schemas.jobs import JobResponse
from hephaes import Workspace

router = APIRouter(prefix="/jobs", tags=["jobs"])
WorkspaceDep = Annotated[Workspace, Depends(get_workspace)]


@router.get("", response_model=list[JobResponse])
def list_jobs_route(workspace: WorkspaceDep) -> list[JobResponse]:
    return [map_job_response(job) for job in workspace.list_jobs()]


@router.get("/{job_id}", response_model=JobResponse)
def get_job_route(job_id: str, workspace: WorkspaceDep) -> JobResponse:
    job = workspace.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"job not found: {job_id}")
    return map_job_response(job)
