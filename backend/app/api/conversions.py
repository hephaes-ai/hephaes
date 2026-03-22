"""Conversion routes for backend-managed hephaes workflows."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api._status import HTTP_422_UNPROCESSABLE_CONTENT
from app.db.models import Conversion
from app.db.session import get_db_session
from app.schemas.conversion_authoring import (
    ConversionAuthoringCapabilitiesResponse,
    ConversionDraftRequest,
    ConversionDraftResponse,
    ConversionInspectionRequest,
    ConversionInspectionResponse,
    ConversionPreviewRequest,
    ConversionPreviewResponse,
)
from app.schemas.conversions import (
    ConversionCreateRequest,
    ConversionDetailResponse,
    ConversionSummaryResponse,
)
from app.schemas.jobs import JobResponse
from app.services.conversion_authoring import (
    ConversionAuthoringInspectionError,
    ConversionAuthoringNotFoundError,
    ConversionAuthoringPreviewError,
    ConversionAuthoringService,
    ConversionAuthoringServiceError,
    ConversionAuthoringValidationError,
)
from app.services.conversions import (
    ConversionExecutionError,
    ConversionNotFoundError,
    ConversionService,
    ConversionValidationError,
    get_conversion_or_raise,
    list_conversions,
)

router = APIRouter(prefix="/conversions", tags=["conversions"])
DbSession = Annotated[Session, Depends(get_db_session)]


def build_conversion_summary_response(conversion: Conversion) -> ConversionSummaryResponse:
    return ConversionSummaryResponse(
        id=conversion.id,
        job_id=conversion.job_id,
        status=conversion.status,
        asset_ids=list(conversion.source_asset_ids_json),
        config=dict(conversion.config_json),
        output_path=conversion.output_path,
        error_message=conversion.error_message,
        created_at=conversion.created_at,
        updated_at=conversion.updated_at,
    )


def build_conversion_detail_response(conversion: Conversion) -> ConversionDetailResponse:
    if conversion.job is None:  # pragma: no cover - defensive integrity guard
        raise ValueError(f"conversion is missing linked job: {conversion.id}")

    return ConversionDetailResponse(
        **build_conversion_summary_response(conversion).model_dump(),
        output_files=list(conversion.output_files_json),
        job=JobResponse.model_validate(conversion.job),
    )


def build_inspection_response(
    *,
    request: ConversionInspectionRequest,
    inspection,
) -> ConversionInspectionResponse:
    return ConversionInspectionResponse(
        asset_id=request.asset_id,
        request=request,
        inspection=inspection,
    )


def build_draft_response(
    *,
    request: ConversionDraftRequest,
    inspection,
    draft,
    draft_revision_id: str | None = None,
) -> ConversionDraftResponse:
    return ConversionDraftResponse(
        asset_id=request.asset_id,
        request=request,
        inspection=inspection,
        draft=draft,
        draft_revision_id=draft_revision_id,
    )


def build_preview_response(
    *,
    request: ConversionPreviewRequest,
    preview,
) -> ConversionPreviewResponse:
    return ConversionPreviewResponse(
        asset_id=request.asset_id,
        request=request,
        preview=preview,
    )


@router.post("", response_model=ConversionDetailResponse, status_code=status.HTTP_201_CREATED)
def create_conversion_route(payload: ConversionCreateRequest, session: DbSession) -> ConversionDetailResponse:
    service = ConversionService(session)

    try:
        conversion = service.run_conversion(payload)
    except ConversionValidationError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except ConversionExecutionError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return build_conversion_detail_response(conversion)


@router.get("/capabilities", response_model=ConversionAuthoringCapabilitiesResponse)
def get_conversion_authoring_capabilities_route(session: DbSession) -> ConversionAuthoringCapabilitiesResponse:
    service = ConversionAuthoringService(session)
    return service.get_capabilities()


@router.post("/inspect", response_model=ConversionInspectionResponse)
def inspect_conversion_route(
    payload: ConversionInspectionRequest,
    session: DbSession,
) -> ConversionInspectionResponse:
    service = ConversionAuthoringService(session)

    try:
        inspection = service.inspect_asset(payload)
    except ConversionAuthoringNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ConversionAuthoringValidationError, ConversionAuthoringInspectionError, ConversionAuthoringServiceError) as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return build_inspection_response(request=payload, inspection=inspection)


@router.post("/draft", response_model=ConversionDraftResponse)
def draft_conversion_route(
    payload: ConversionDraftRequest,
    session: DbSession,
) -> ConversionDraftResponse:
    service = ConversionAuthoringService(session)

    try:
        inspection, draft, draft_revision_id = service.draft_asset(payload)
    except ConversionAuthoringNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ConversionAuthoringValidationError, ConversionAuthoringInspectionError, ConversionAuthoringServiceError) as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return build_draft_response(
        request=payload,
        inspection=inspection,
        draft=draft,
        draft_revision_id=draft_revision_id,
    )


@router.post("/preview", response_model=ConversionPreviewResponse)
def preview_conversion_route(
    payload: ConversionPreviewRequest,
    session: DbSession,
) -> ConversionPreviewResponse:
    service = ConversionAuthoringService(session)

    try:
        preview = service.preview_asset(payload)
    except ConversionAuthoringNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ConversionAuthoringValidationError, ConversionAuthoringPreviewError, ConversionAuthoringServiceError) as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return build_preview_response(request=payload, preview=preview)


@router.get("", response_model=list[ConversionSummaryResponse])
def list_conversions_route(session: DbSession) -> list[ConversionSummaryResponse]:
    return [
        build_conversion_summary_response(conversion)
        for conversion in list_conversions(session)
    ]


@router.get("/{conversion_id}", response_model=ConversionDetailResponse)
def get_conversion_route(conversion_id: str, session: DbSession) -> ConversionDetailResponse:
    try:
        conversion = get_conversion_or_raise(session, conversion_id)
    except ConversionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return build_conversion_detail_response(conversion)
