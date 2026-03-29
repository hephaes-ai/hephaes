"""Dashboard summary routes for backend-owned operational rollups."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_workspace
from app.schemas.dashboard import (
    DashboardBlockersResponse,
    DashboardSummaryResponse,
    DashboardTrendsResponse,
)
from app.services.dashboard import (
    get_dashboard_blockers,
    get_dashboard_summary,
    get_dashboard_trends,
)
from hephaes import Workspace

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
WorkspaceDep = Annotated[Workspace, Depends(get_workspace)]


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary_route(workspace: WorkspaceDep) -> DashboardSummaryResponse:
    return get_dashboard_summary(workspace)


@router.get("/trends", response_model=DashboardTrendsResponse)
def get_dashboard_trends_route(
    workspace: WorkspaceDep,
    days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> DashboardTrendsResponse:
    return get_dashboard_trends(workspace, days=days)


@router.get("/blockers", response_model=DashboardBlockersResponse)
def get_dashboard_blockers_route(workspace: WorkspaceDep) -> DashboardBlockersResponse:
    return get_dashboard_blockers(workspace)
