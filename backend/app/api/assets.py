"""Asset routes backed by the package-owned workspace."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import ValidationError

from app.api._status import HTTP_422_UNPROCESSABLE_CONTENT
from app.dependencies import get_workspace
from app.mappers.workspace import (
    asset_display_path,
    map_asset_list_item,
    map_asset_metadata,
    map_asset_summary,
    map_conversion_summary,
    map_job_response,
    map_tag_response,
)
from app.schemas.assets import (
    AssetDetailResponse,
    AssetListItem,
    AssetListQueryParams,
    AssetRegistrationRequest,
    AssetRegistrationResponse,
    AssetRegistrationSkip,
    AssetSummary,
    AssetTagAttachRequest,
    DialogAssetRegistrationResponse,
    DirectoryScanRequest,
    DirectoryScanResponse,
    ReindexAllResponse,
)
from app.schemas.conversions import ConversionSummaryResponse
from app.schemas.jobs import JobResponse
from app.services import assets as asset_services
from app.services import indexing as indexing_service
from hephaes import (
    AssetAlreadyRegisteredError,
    AssetNotFoundError,
    InvalidAssetPathError,
    TagNotFoundError,
    Workspace,
)

router = APIRouter(prefix="/assets", tags=["assets"])
WorkspaceDep = Annotated[Workspace, Depends(get_workspace)]


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
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(),
        ) from exc


def _asset_registration_response(asset) -> AssetRegistrationResponse:
    return AssetRegistrationResponse.model_validate(map_asset_summary(asset).model_dump())


def _index_workspace_asset(
    workspace: Workspace,
    asset_id: str,
    *,
    job_config: dict,
):
    asset = workspace.get_asset_or_raise(asset_id)
    return workspace.index_asset(
        asset_id,
        job_config=job_config,
        profile_path=asset.file_path,
        profile_fn=indexing_service.profile_asset_file,
    )


def _related_jobs(
    workspace: Workspace,
    *,
    asset_id: str,
    limit: int = 10,
) -> list[JobResponse]:
    responses = [
        map_job_response(job)
        for job in workspace.list_jobs()
        if asset_id in job.target_asset_ids
    ]
    return sorted(
        responses,
        key=lambda job: (job.created_at, job.id),
        reverse=True,
    )[:limit]


def _related_conversions(
    workspace: Workspace,
    *,
    asset_id: str,
    limit: int = 10,
) -> list[ConversionSummaryResponse]:
    responses = [
        map_conversion_summary(run)
        for run in workspace.list_conversion_runs()
        if asset_id in run.source_asset_ids
    ]
    return sorted(
        responses,
        key=lambda conversion: (conversion.created_at, conversion.id),
        reverse=True,
    )[:limit]


def _build_asset_detail_response(
    workspace: Workspace,
    asset_id: str,
) -> AssetDetailResponse:
    asset = workspace.get_asset_or_raise(asset_id)
    metadata = workspace.get_asset_metadata(asset_id)
    tags = workspace.get_asset_tags(asset_id)
    return AssetDetailResponse(
        asset=map_asset_summary(asset),
        metadata=map_asset_metadata(metadata) if metadata is not None else None,
        tags=[map_tag_response(tag) for tag in tags],
        related_jobs=_related_jobs(workspace, asset_id=asset_id),
        conversions=_related_conversions(workspace, asset_id=asset_id),
    )


def _matches_asset_query(
    workspace: Workspace,
    asset,
    query: AssetListQueryParams,
) -> bool:
    if query.search is not None:
        haystack = " ".join(
            (
                asset.file_name.lower(),
                asset.file_type.lower(),
                asset_display_path(asset).lower(),
            )
        )
        if query.search.lower() not in haystack:
            return False

    if query.file_type is not None and asset.file_type.lower() != query.file_type.lower():
        return False

    if query.status is not None and asset.indexing_status != query.status:
        return False

    metadata = workspace.get_asset_metadata(asset.id)
    if query.min_duration is not None:
        if metadata is None or metadata.duration is None or metadata.duration < query.min_duration:
            return False
    if query.max_duration is not None:
        if metadata is None or metadata.duration is None or metadata.duration > query.max_duration:
            return False
    if query.start_after is not None:
        if metadata is None or metadata.start_time is None or metadata.start_time < query.start_after:
            return False
    if query.start_before is not None:
        if metadata is None or metadata.start_time is None or metadata.start_time > query.start_before:
            return False

    return True


def _import_asset_or_skip(
    workspace: Workspace,
    file_path: str,
) -> tuple[AssetRegistrationResponse | None, AssetRegistrationSkip | None]:
    try:
        asset = workspace.register_asset(file_path)
    except InvalidAssetPathError as exc:
        return None, AssetRegistrationSkip(
            detail=str(exc),
            file_path=file_path,
            reason="invalid_path",
        )
    except AssetAlreadyRegisteredError as exc:
        return None, AssetRegistrationSkip(
            detail=str(exc),
            file_path=file_path,
            reason="duplicate",
        )
    return _asset_registration_response(asset), None


@router.post(
    "/register",
    response_model=AssetRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_asset_route(
    payload: AssetRegistrationRequest,
    workspace: WorkspaceDep,
) -> AssetRegistrationResponse:
    try:
        asset = workspace.register_asset(payload.file_path)
    except InvalidAssetPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AssetAlreadyRegisteredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return _asset_registration_response(asset)


@router.post(
    "/upload",
    response_model=AssetRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_asset_route(
    request: Request,
    workspace: WorkspaceDep,
    file_name: Annotated[str | None, Header(alias="X-File-Name")] = None,
) -> AssetRegistrationResponse:
    if file_name is None or not file_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="x-file-name header is required for asset uploads",
        )

    content = await request.body()

    try:
        normalized_file_name = asset_services.normalize_uploaded_file_name(file_name)
        if not content:
            raise asset_services.InvalidAssetUploadError("uploaded file is empty")
    except asset_services.InvalidAssetUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    raw_target_path = request.app.state.settings.raw_data_dir / normalized_file_name
    if raw_target_path.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"asset already registered: {raw_target_path}",
        )

    raw_target_path.parent.mkdir(parents=True, exist_ok=True)
    raw_target_path.write_bytes(content)
    try:
        asset = workspace.register_asset(str(raw_target_path))
    except AssetAlreadyRegisteredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception:
        raw_target_path.unlink(missing_ok=True)
        raise

    return _asset_registration_response(asset)


@router.post("/register-dialog", response_model=DialogAssetRegistrationResponse)
def register_assets_from_dialog_route(
    workspace: WorkspaceDep,
) -> DialogAssetRegistrationResponse:
    try:
        selected_paths = asset_services.open_asset_file_dialog()
    except asset_services.AssetDialogUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    if not selected_paths:
        return DialogAssetRegistrationResponse(
            canceled=True,
            registered_assets=[],
            skipped=[],
        )

    registered_assets: list[AssetRegistrationResponse] = []
    skipped: list[AssetRegistrationSkip] = []
    for file_path in selected_paths:
        registered_asset, skipped_item = _import_asset_or_skip(workspace, file_path)
        if registered_asset is not None:
            registered_assets.append(registered_asset)
        if skipped_item is not None:
            skipped.append(skipped_item)

    return DialogAssetRegistrationResponse(
        canceled=False,
        registered_assets=registered_assets,
        skipped=skipped,
    )


@router.post("/scan-directory", response_model=DirectoryScanResponse)
def scan_directory_route(
    payload: DirectoryScanRequest,
    workspace: WorkspaceDep,
) -> DirectoryScanResponse:
    directory = asset_services.normalize_asset_path(payload.directory_path)
    if not directory.exists() or not directory.is_dir():
        detail = (
            f"asset directory does not exist: {directory}"
            if not directory.exists()
            else f"asset directory is not a directory: {directory}"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    candidates = list(asset_services._iter_supported_asset_files(directory, recursive=payload.recursive))
    registered_assets: list[AssetRegistrationResponse] = []
    skipped: list[AssetRegistrationSkip] = []
    for candidate in candidates:
        registered_asset, skipped_item = _import_asset_or_skip(workspace, str(candidate))
        if registered_asset is not None:
            registered_assets.append(registered_asset)
        if skipped_item is not None:
            skipped.append(skipped_item)

    return DirectoryScanResponse(
        discovered_file_count=len(candidates),
        recursive=payload.recursive,
        registered_assets=registered_assets,
        scanned_directory=str(directory),
        skipped=skipped,
    )


@router.post("/{asset_id}/index", response_model=AssetDetailResponse)
def index_asset_route(
    asset_id: str,
    request: Request,
    workspace: WorkspaceDep,
) -> AssetDetailResponse:
    try:
        _index_workspace_asset(
            workspace,
            asset_id,
            job_config={
                "execution": request.app.state.settings.job_execution_mode,
                "trigger": "index_asset",
            },
        )
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return _build_asset_detail_response(workspace, asset_id)


@router.post("/{asset_id}/tags", response_model=AssetDetailResponse)
def attach_tag_to_asset_route(
    asset_id: str,
    payload: AssetTagAttachRequest,
    workspace: WorkspaceDep,
) -> AssetDetailResponse:
    try:
        asset = workspace.get_asset_or_raise(asset_id)
        tag = workspace.resolve_tag(payload.tag_id)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    current_tags = workspace.get_asset_tags(asset.id)
    if any(existing_tag.id == tag.id for existing_tag in current_tags):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"tag already attached to asset: {tag.name} -> {asset.file_name}",
        )

    workspace.attach_tag_to_asset(asset.id, tag.id)
    return _build_asset_detail_response(workspace, asset.id)


@router.delete("/{asset_id}/tags/{tag_id}", response_model=AssetDetailResponse)
def remove_tag_from_asset_route(
    asset_id: str,
    tag_id: str,
    workspace: WorkspaceDep,
) -> AssetDetailResponse:
    try:
        asset = workspace.get_asset_or_raise(asset_id)
        tag = workspace.resolve_tag(tag_id)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    current_tags = workspace.get_asset_tags(asset.id)
    if not any(existing_tag.id == tag.id for existing_tag in current_tags):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"tag not attached to asset: {tag.name} -> {asset.file_name}",
        )

    workspace.remove_tag_from_asset(asset.id, tag.id)
    attached_elsewhere = any(
        any(existing_tag.id == tag.id for existing_tag in workspace.get_asset_tags(other_asset.id))
        for other_asset in workspace.list_assets()
    )
    if not attached_elsewhere:
        workspace.delete_tag(tag.id)
    return _build_asset_detail_response(workspace, asset.id)


@router.post("/reindex-all", response_model=ReindexAllResponse)
def reindex_all_route(
    request: Request,
    workspace: WorkspaceDep,
) -> ReindexAllResponse:
    indexed_assets: list[AssetSummary] = []
    failed_assets: list[AssetSummary] = []

    assets = list(workspace.list_assets())
    for asset in reversed(assets):
        if asset.indexing_status not in {"pending", "failed"} and asset.last_indexed_at is not None:
            continue
        try:
            reindexed_asset = _index_workspace_asset(
                workspace,
                asset.id,
                job_config={
                    "execution": request.app.state.settings.job_execution_mode,
                    "trigger": "reindex_all",
                },
            )
            indexed_assets.append(
                map_asset_summary(reindexed_asset)
            )
        except Exception:
            failed_assets.append(map_asset_summary(workspace.get_asset_or_raise(asset.id)))

    return ReindexAllResponse(
        failed_assets=failed_assets,
        indexed_assets=indexed_assets,
        total_requested=len(failed_assets) + len(indexed_assets),
    )


@router.get("", response_model=list[AssetListItem])
def list_assets_route(
    query: Annotated[AssetListQueryParams, Depends(parse_list_assets_query)],
    workspace: WorkspaceDep,
) -> list[AssetListItem]:
    tag_filters = [query.tag] if query.tag is not None else None
    assets = [
        asset
        for asset in workspace.list_assets(tags=tag_filters)
        if _matches_asset_query(workspace, asset, query)
    ]
    return [
        map_asset_list_item(asset, tags=workspace.get_asset_tags(asset.id))
        for asset in assets
    ]


@router.get("/{asset_id}", response_model=AssetDetailResponse)
def get_asset_route(asset_id: str, workspace: WorkspaceDep) -> AssetDetailResponse:
    try:
        return _build_asset_detail_response(workspace, asset_id)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
