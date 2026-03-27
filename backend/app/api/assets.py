"""Asset routes backed by the package-owned workspace."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api._status import HTTP_422_UNPROCESSABLE_CONTENT
from app.dependencies import get_db_session, get_workspace
from app.mappers.workspace import (
    asset_display_path,
    map_asset_list_item,
    map_asset_metadata,
    map_asset_summary,
    map_conversion_summary,
    map_episode_summary,
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
    EpisodeSummaryResponse,
    ReindexAllResponse,
)
from app.schemas.conversions import ConversionSummaryResponse
from app.schemas.jobs import JobResponse
from app.services import assets as asset_services
from app.services import indexing as indexing_service
from app.services.assets import (
    list_related_conversions_for_asset,
    list_related_jobs_for_asset,
    sync_workspace_asset,
)
from app.services.jobs import sync_workspace_job
from hephaes import (
    AssetAlreadyRegisteredError,
    AssetNotFoundError,
    InvalidAssetPathError,
    TagNotFoundError,
    Workspace,
)
import hephaes.workspace as workspace_module

router = APIRouter(prefix="/assets", tags=["assets"])
WorkspaceDep = Annotated[Workspace, Depends(get_workspace)]
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
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(),
        ) from exc


def _asset_registration_response(asset) -> AssetRegistrationResponse:
    return AssetRegistrationResponse.model_validate(map_asset_summary(asset).model_dump())


def _configure_workspace_indexing_adapter(workspace: Workspace) -> None:
    def _profile(file_path: str, *, max_workers: int = 1):
        del max_workers
        resolved_file_path = file_path
        asset = workspace.find_asset_by_path(file_path)
        if asset is not None and asset.source_path is not None:
            resolved_file_path = asset.source_path
        return indexing_service.profile_asset_file(resolved_file_path)

    workspace_module.profile_asset_file = _profile


def _related_jobs(
    workspace: Workspace,
    *,
    asset_id: str,
    session: Session | None = None,
    limit: int = 10,
) -> list[JobResponse]:
    responses = {
        job.id: map_job_response(job)
        for job in workspace.list_jobs()
        if asset_id in job.target_asset_ids
    }
    if session is not None:
        for job in list_related_jobs_for_asset(session, asset_id=asset_id, limit=limit):
            payload = JobResponse.model_validate(job).model_dump()
            config_payload = payload.get("config_json")
            if isinstance(config_payload, dict):
                payload["representation_policy"] = config_payload.get("representation_policy")
            responses.setdefault(job.id, JobResponse.model_validate(payload))
    return sorted(
        responses.values(),
        key=lambda job: (job.created_at, job.id),
        reverse=True,
    )[:limit]


def _related_conversions(
    workspace: Workspace,
    *,
    asset_id: str,
    session: Session | None = None,
    limit: int = 10,
) -> list[ConversionSummaryResponse]:
    responses = {
        run.id: map_conversion_summary(run)
        for run in workspace.list_conversion_runs()
        if asset_id in run.source_asset_ids
    }
    if session is not None:
        for conversion in list_related_conversions_for_asset(session, asset_id=asset_id, limit=limit):
            responses.setdefault(
                conversion.id,
                ConversionSummaryResponse(
                    id=conversion.id,
                    job_id=conversion.job_id,
                    status=conversion.status,
                    asset_ids=list(conversion.source_asset_ids_json),
                    config=dict(conversion.config_json),
                    output_path=conversion.output_path,
                    error_message=conversion.error_message,
                    representation_policy=None,
                    created_at=conversion.created_at,
                    updated_at=conversion.updated_at,
                ),
            )
    return list(responses.values())[:limit]


def _build_asset_detail_response(
    workspace: Workspace,
    asset_id: str,
    *,
    session: Session | None = None,
) -> AssetDetailResponse:
    asset = workspace.get_asset_or_raise(asset_id)
    metadata = workspace.get_asset_metadata(asset_id)
    tags = workspace.get_asset_tags(asset_id)
    return AssetDetailResponse(
        asset=map_asset_summary(asset),
        metadata=map_asset_metadata(metadata) if metadata is not None else None,
        tags=[map_tag_response(tag) for tag in tags],
        episodes=map_episode_summary(metadata) if metadata is not None else [],
        related_jobs=_related_jobs(workspace, asset_id=asset_id, session=session),
        conversions=_related_conversions(workspace, asset_id=asset_id, session=session),
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
        asset = workspace.import_asset(file_path)
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
    session: DbSession,
) -> AssetRegistrationResponse:
    try:
        asset = workspace.import_asset(payload.file_path)
    except InvalidAssetPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AssetAlreadyRegisteredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    sync_workspace_asset(session, asset=asset)
    return _asset_registration_response(asset)


@router.post(
    "/upload",
    response_model=AssetRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_asset_route(
    request: Request,
    workspace: WorkspaceDep,
    session: DbSession,
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
        asset = workspace.import_asset(str(raw_target_path))
    except Exception:
        raw_target_path.unlink(missing_ok=True)
        raise

    sync_workspace_asset(session, asset=asset)
    return _asset_registration_response(asset)


@router.post("/register-dialog", response_model=DialogAssetRegistrationResponse)
def register_assets_from_dialog_route(
    workspace: WorkspaceDep,
    session: DbSession,
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
            sync_workspace_asset(
                session,
                asset=workspace.get_asset_or_raise(registered_asset.id),
            )
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
    session: DbSession,
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
            sync_workspace_asset(
                session,
                asset=workspace.get_asset_or_raise(registered_asset.id),
            )
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
    session: DbSession,
) -> AssetDetailResponse:
    try:
        _configure_workspace_indexing_adapter(workspace)
        workspace.index_asset(
            asset_id,
            job_config={
                "execution": request.app.state.settings.job_execution_mode,
                "trigger": "index_asset",
            },
        )
        sync_workspace_asset(
            session,
            asset=workspace.get_asset_or_raise(asset_id),
            metadata=workspace.get_asset_metadata(asset_id),
        )
        for job in workspace.list_jobs():
            if asset_id in job.target_asset_ids and job.kind == "index_asset":
                sync_workspace_job(session, job=job)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        try:
            sync_workspace_asset(
                session,
                asset=workspace.get_asset_or_raise(asset_id),
                metadata=workspace.get_asset_metadata(asset_id),
            )
            for job in workspace.list_jobs():
                if asset_id in job.target_asset_ids and job.kind == "index_asset":
                    sync_workspace_job(session, job=job)
        except Exception:
            pass
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return _build_asset_detail_response(workspace, asset_id, session=session)


@router.post("/{asset_id}/tags", response_model=AssetDetailResponse)
def attach_tag_to_asset_route(
    asset_id: str,
    payload: AssetTagAttachRequest,
    workspace: WorkspaceDep,
    session: DbSession,
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
    return _build_asset_detail_response(workspace, asset.id, session=session)


@router.delete("/{asset_id}/tags/{tag_id}", response_model=AssetDetailResponse)
def remove_tag_from_asset_route(
    asset_id: str,
    tag_id: str,
    workspace: WorkspaceDep,
    session: DbSession,
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
    return _build_asset_detail_response(workspace, asset.id, session=session)


@router.post("/reindex-all", response_model=ReindexAllResponse)
def reindex_all_route(
    request: Request,
    workspace: WorkspaceDep,
    session: DbSession,
) -> ReindexAllResponse:
    indexed_assets: list[AssetSummary] = []
    failed_assets: list[AssetSummary] = []

    assets = list(workspace.list_assets())
    for asset in reversed(assets):
        if asset.indexing_status not in {"pending", "failed"} and asset.last_indexed_at is not None:
            continue
        try:
            _configure_workspace_indexing_adapter(workspace)
            reindexed_asset = workspace.index_asset(
                asset.id,
                job_config={
                    "execution": request.app.state.settings.job_execution_mode,
                    "trigger": "reindex_all",
                },
            )
            sync_workspace_asset(
                session,
                asset=reindexed_asset,
                metadata=workspace.get_asset_metadata(asset.id),
            )
            for job in workspace.list_jobs():
                if asset.id in job.target_asset_ids and job.kind == "index_asset":
                    sync_workspace_job(session, job=job)
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


@router.get("/{asset_id}/episodes", response_model=list[EpisodeSummaryResponse])
def get_asset_episodes_route(asset_id: str, workspace: WorkspaceDep):
    try:
        workspace.get_asset_or_raise(asset_id)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    metadata = workspace.get_asset_metadata(asset_id)
    if metadata is None or metadata.default_episode is None:
        asset = workspace.get_asset_or_raise(asset_id)
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"asset must be indexed before episodes are available: {asset.file_name}",
        )
    return map_episode_summary(metadata)


@router.get("/{asset_id}", response_model=AssetDetailResponse)
def get_asset_route(asset_id: str, workspace: WorkspaceDep, session: DbSession) -> AssetDetailResponse:
    try:
        return _build_asset_detail_response(workspace, asset_id, session=session)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
