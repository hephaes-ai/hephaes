"""Dashboard summary routes for backend-owned operational rollups."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db_session, get_workspace
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
DbSession = Annotated[Session, Depends(get_db_session)]


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary_route(workspace: WorkspaceDep, session: DbSession) -> DashboardSummaryResponse:
    return get_dashboard_summary(workspace, session)


@router.get("/trends", response_model=DashboardTrendsResponse)
def get_dashboard_trends_route(
    workspace: WorkspaceDep,
    session: DbSession,
    days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> DashboardTrendsResponse:
    return get_dashboard_trends(workspace, session, days=days)


@router.get("/blockers", response_model=DashboardBlockersResponse)
def get_dashboard_blockers_route(workspace: WorkspaceDep, session: DbSession) -> DashboardBlockersResponse:
    return get_dashboard_blockers(workspace, session)
