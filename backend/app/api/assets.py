"""Asset routes for the backend application."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.app.db.models import Asset
from backend.app.db.session import get_db_session
from backend.app.schemas.assets import (
    AssetDetailResponse,
    AssetListQueryParams,
    AssetMetadataResponse,
    AssetTagAttachRequest,
    DefaultEpisodeSummary,
    DialogAssetRegistrationResponse,
    IndexedTopicSummary,
    AssetListItem,
    AssetRegistrationRequest,
    AssetRegistrationResponse,
    ReindexAllResponse,
    AssetSummary,
    TagResponse,
    VisualizationSummary,
)
from backend.app.services.assets import (
    AssetAlreadyRegisteredError,
    AssetDialogUnavailableError,
    AssetListFilters,
    AssetNotFoundError,
    InvalidAssetPathError,
    get_asset_or_raise,
    list_assets,
    register_asset,
    register_assets_from_dialog,
)
from backend.app.services.indexing import AssetIndexingError, IndexingService
from backend.app.services.tags import (
    AssetTagAlreadyExistsError,
    AssetTagNotFoundError,
    TagNotFoundError,
    attach_tag_to_asset,
    remove_tag_from_asset,
)

router = APIRouter(prefix="/assets", tags=["assets"])
DbSession = Annotated[Session, Depends(get_db_session)]


def parse_list_assets_query(
    search: Annotated[str | None, Query()] = None,
    tag: Annotated[str | None, Query()] = None,
    file_type: Annotated[str | None, Query(alias="type")] = None,
    status_value: Annotated[str | None, Query(alias="status")] = None,
    min_duration: Annotated[str | None, Query()] = None,
    max_duration: Annotated[str | None, Query()] = None,
    start_after: Annotated[str | None, Query()] = None,
    start_before: Annotated[str | None, Query()] = None,
) -> AssetListQueryParams:
    try:
        return AssetListQueryParams.model_validate(
            {
                "search": search,
                "tag": tag,
                "type": file_type,
                "status": status_value,
                "min_duration": min_duration,
                "max_duration": max_duration,
                "start_after": start_after,
                "start_before": start_before,
            }
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(),
        ) from exc


def build_asset_detail_response(asset: Asset) -> AssetDetailResponse:
    metadata_record = asset.metadata_record
    metadata: AssetMetadataResponse | None = None

    if metadata_record is not None:
        metadata = AssetMetadataResponse(
            default_episode=(
                DefaultEpisodeSummary.model_validate(metadata_record.default_episode_json)
                if metadata_record.default_episode_json is not None
                else None
            ),
            duration=metadata_record.duration,
            end_time=metadata_record.end_time,
            indexing_error=metadata_record.indexing_error,
            message_count=metadata_record.message_count,
            raw_metadata=metadata_record.raw_metadata_json,
            sensor_types=metadata_record.sensor_types_json,
            start_time=metadata_record.start_time,
            topic_count=metadata_record.topic_count,
            topics=[
                IndexedTopicSummary.model_validate(topic_payload)
                for topic_payload in metadata_record.topics_json
            ],
            visualization_summary=(
                VisualizationSummary.model_validate(metadata_record.visualization_summary_json)
                if metadata_record.visualization_summary_json is not None
                else None
            ),
        )

    return AssetDetailResponse(
        asset=AssetSummary.model_validate(asset),
        metadata=metadata,
        tags=[TagResponse.model_validate(tag) for tag in asset.tags],
    )


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


@router.post("/{asset_id}/index", response_model=AssetDetailResponse)
def index_asset_route(asset_id: str, session: DbSession) -> AssetDetailResponse:
    indexing_service = IndexingService(session)

    try:
        asset = indexing_service.index_asset(asset_id)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AssetIndexingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return build_asset_detail_response(asset)


@router.post("/{asset_id}/tags", response_model=AssetDetailResponse)
def attach_tag_to_asset_route(
    asset_id: str,
    payload: AssetTagAttachRequest,
    session: DbSession,
) -> AssetDetailResponse:
    try:
        asset = attach_tag_to_asset(session, asset_id=asset_id, tag_id=payload.tag_id)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AssetTagAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return build_asset_detail_response(asset)


@router.delete("/{asset_id}/tags/{tag_id}", response_model=AssetDetailResponse)
def remove_tag_from_asset_route(asset_id: str, tag_id: str, session: DbSession) -> AssetDetailResponse:
    try:
        asset = remove_tag_from_asset(session, asset_id=asset_id, tag_id=tag_id)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AssetTagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return build_asset_detail_response(asset)


@router.post("/reindex-all", response_model=ReindexAllResponse)
def reindex_all_route(session: DbSession) -> ReindexAllResponse:
    indexing_service = IndexingService(session)
    result = indexing_service.reindex_all_pending_assets()

    return ReindexAllResponse(
        failed_assets=[
            AssetSummary.model_validate(asset)
            for asset in result.failed_assets
        ],
        indexed_assets=[
            AssetSummary.model_validate(asset)
            for asset in result.indexed_assets
        ],
        total_requested=len(result.failed_assets) + len(result.indexed_assets),
    )


@router.get("", response_model=list[AssetListItem])
def list_assets_route(
    query: Annotated[AssetListQueryParams, Depends(parse_list_assets_query)],
    session: DbSession,
) -> list[AssetListItem]:
    assets = list_assets(
        session,
        filters=AssetListFilters(
            search=query.search,
            tag=query.tag,
            file_type=query.file_type,
            status=query.status,
            min_duration=query.min_duration,
            max_duration=query.max_duration,
            start_after=query.start_after,
            start_before=query.start_before,
        ),
    )
    return [
        AssetListItem(
            **AssetSummary.model_validate(asset).model_dump(),
            tags=[TagResponse.model_validate(tag) for tag in asset.tags],
        )
        for asset in assets
    ]


@router.get("/{asset_id}", response_model=AssetDetailResponse)
def get_asset_route(asset_id: str, session: DbSession) -> AssetDetailResponse:
    try:
        asset = get_asset_or_raise(session, asset_id)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return build_asset_detail_response(asset)
