"""Asset routes for the backend application."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db_session
from backend.app.schemas.assets import (
    AssetDetailResponse,
    DialogAssetRegistrationResponse,
    AssetListItem,
    AssetRegistrationRequest,
    AssetRegistrationResponse,
    AssetSummary,
)
from backend.app.services.assets import (
    AssetAlreadyRegisteredError,
    AssetDialogUnavailableError,
    AssetNotFoundError,
    InvalidAssetPathError,
    get_asset_or_raise,
    list_assets,
    register_asset,
    register_assets_from_dialog,
)

router = APIRouter(prefix="/assets", tags=["assets"])
DbSession = Annotated[Session, Depends(get_db_session)]


@router.post(
    "/register",
    response_model=AssetRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_asset_route(payload: AssetRegistrationRequest, session: DbSession) -> AssetRegistrationResponse:
    try:
        asset = register_asset(session, file_path=payload.file_path)
    except InvalidAssetPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AssetAlreadyRegisteredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return AssetRegistrationResponse.model_validate(asset)


@router.post("/register-dialog", response_model=DialogAssetRegistrationResponse)
def register_assets_from_dialog_route(session: DbSession) -> DialogAssetRegistrationResponse:
    try:
        result = register_assets_from_dialog(session)
    except AssetDialogUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return DialogAssetRegistrationResponse(
        canceled=result.canceled,
        registered_assets=[
            AssetRegistrationResponse.model_validate(asset) for asset in result.registered_assets
        ],
        skipped=[
            {
                "detail": item.detail,
                "file_path": item.file_path,
                "reason": item.reason,
            }
            for item in result.skipped
        ],
    )


@router.get("", response_model=list[AssetListItem])
def list_assets_route(session: DbSession) -> list[AssetListItem]:
    assets = list_assets(session)
    return [AssetListItem.model_validate(asset) for asset in assets]


@router.get("/{asset_id}", response_model=AssetDetailResponse)
def get_asset_route(asset_id: str, session: DbSession) -> AssetDetailResponse:
    try:
        asset = get_asset_or_raise(session, asset_id)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return AssetDetailResponse(asset=AssetSummary.model_validate(asset))
