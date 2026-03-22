"""Routes for saved conversion config persistence and lifecycle management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api._status import HTTP_422_UNPROCESSABLE_CONTENT
from app.db.session import get_db_session
from app.schemas.conversion_authoring import (
    SavedConversionConfigCreateRequest,
    SavedConversionConfigDetailResponse,
    SavedConversionConfigDuplicateRequest,
    SavedConversionConfigSummaryResponse,
    SavedConversionConfigUpdateRequest,
)
from app.services.conversion_configs import (
    ConversionConfigInvalidError,
    ConversionConfigNotFoundError,
    ConversionConfigService,
    ConversionConfigServiceError,
    ConversionConfigValidationError,
)

router = APIRouter(prefix="/conversion-configs", tags=["conversion-configs"])
DbSession = Annotated[Session, Depends(get_db_session)]


@router.get("", response_model=list[SavedConversionConfigSummaryResponse])
def list_conversion_configs_route(session: DbSession) -> list[SavedConversionConfigSummaryResponse]:
    service = ConversionConfigService(session)
    return service.list_saved_configs()


@router.post("", response_model=SavedConversionConfigDetailResponse, status_code=status.HTTP_201_CREATED)
def create_conversion_config_route(
    payload: SavedConversionConfigCreateRequest,
    session: DbSession,
) -> SavedConversionConfigDetailResponse:
    service = ConversionConfigService(session)

    try:
        return service.create_saved_config(payload)
    except (ConversionConfigValidationError, ConversionConfigServiceError) as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get("/{config_id}", response_model=SavedConversionConfigDetailResponse)
def get_conversion_config_route(config_id: str, session: DbSession) -> SavedConversionConfigDetailResponse:
    service = ConversionConfigService(session)

    try:
        return service.get_saved_config(config_id)
    except ConversionConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConversionConfigInvalidError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.patch("/{config_id}", response_model=SavedConversionConfigDetailResponse)
def update_conversion_config_route(
    config_id: str,
    payload: SavedConversionConfigUpdateRequest,
    session: DbSession,
) -> SavedConversionConfigDetailResponse:
    service = ConversionConfigService(session)

    try:
        return service.update_saved_config(config_id, payload)
    except ConversionConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ConversionConfigInvalidError, ConversionConfigValidationError, ConversionConfigServiceError) as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/{config_id}/duplicate", response_model=SavedConversionConfigDetailResponse, status_code=status.HTTP_201_CREATED)
def duplicate_conversion_config_route(
    config_id: str,
    payload: SavedConversionConfigDuplicateRequest,
    session: DbSession,
) -> SavedConversionConfigDetailResponse:
    service = ConversionConfigService(session)

    try:
        return service.duplicate_saved_config(config_id, payload)
    except ConversionConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ConversionConfigInvalidError, ConversionConfigValidationError, ConversionConfigServiceError) as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
