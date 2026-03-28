"""Routes for saved conversion config persistence and lifecycle management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api._status import HTTP_422_UNPROCESSABLE_CONTENT
from app.dependencies import get_workspace
from app.mappers.workspace import map_saved_conversion_config_detail, map_saved_conversion_config_summary
from app.schemas.conversion_authoring import (
    SavedConversionConfigCreateRequest,
    SavedConversionConfigDetailResponse,
    SavedConversionConfigDuplicateRequest,
    SavedConversionConfigSummaryResponse,
    SavedConversionConfigUpdateRequest,
)
from hephaes import (
    ConversionConfigAlreadyExistsError,
    ConversionConfigNotFoundError,
    Workspace,
    build_conversion_spec_document,
)

router = APIRouter(prefix="/conversion-configs", tags=["conversion-configs"])
WorkspaceDep = Annotated[Workspace, Depends(get_workspace)]


def _build_config_document(*, spec, metadata: dict | None):
    return build_conversion_spec_document(spec, metadata=metadata or {})


def _build_saved_config_detail_response(
    workspace: Workspace,
    config_selector: str,
) -> SavedConversionConfigDetailResponse:
    config = workspace.resolve_saved_conversion_config(config_selector)
    revisions = [
        workspace.get_saved_conversion_config_revision(revision.id)
        for revision in workspace.list_saved_conversion_config_revisions(config_selector)
    ]
    draft_revisions = [
        workspace.get_conversion_draft_revision(draft.id)
        for draft in workspace.list_conversion_draft_revisions(saved_config_selector=config_selector)
    ]
    return map_saved_conversion_config_detail(
        config,
        revisions=[revision for revision in revisions if revision is not None],
        draft_revisions=[draft for draft in draft_revisions if draft is not None],
    )


def _build_saved_config_summary_response(
    workspace: Workspace,
    config_id: str,
) -> SavedConversionConfigSummaryResponse:
    summary = next(
        config for config in workspace.list_saved_conversion_configs() if config.id == config_id
    )
    resolved = workspace.resolve_saved_conversion_config(config_id)
    revisions = [
        workspace.get_saved_conversion_config_revision(revision.id)
        for revision in workspace.list_saved_conversion_config_revisions(config_id)
    ]
    resolved_revisions = [revision for revision in revisions if revision is not None]
    draft_revisions = [
        workspace.get_conversion_draft_revision(draft.id)
        for draft in workspace.list_conversion_draft_revisions(saved_config_selector=config_id)
    ]
    latest_preview_revision = next(
        (draft for draft in draft_revisions if draft is not None and draft.preview_json is not None),
        None,
    )
    return map_saved_conversion_config_summary(
        summary,
        revision_count=len(resolved_revisions),
        draft_count=len([draft for draft in draft_revisions if draft is not None]),
        migration_notes=[
            revision.description
            for revision in resolved_revisions
            if revision.description is not None and "migrat" in revision.description.casefold()
        ],
        resolved_config=resolved,
        latest_preview_available=latest_preview_revision is not None,
        latest_preview_updated_at=(
            latest_preview_revision.updated_at if latest_preview_revision is not None else None
        ),
    )


def _next_duplicate_name(workspace: Workspace, base_name: str) -> str:
    candidate = base_name
    suffix = 2
    existing_names = {config.name.casefold(): config.id for config in workspace.list_saved_conversion_configs()}
    while candidate.casefold() in existing_names:
        candidate = f"{base_name} ({suffix})"
        suffix += 1
    return candidate


@router.get("", response_model=list[SavedConversionConfigSummaryResponse])
def list_conversion_configs_route(workspace: WorkspaceDep) -> list[SavedConversionConfigSummaryResponse]:
    return [
        _build_saved_config_summary_response(workspace, config.id)
        for config in workspace.list_saved_conversion_configs()
    ]


@router.post("", response_model=SavedConversionConfigDetailResponse, status_code=status.HTTP_201_CREATED)
def create_conversion_config_route(
    payload: SavedConversionConfigCreateRequest,
    workspace: WorkspaceDep,
) -> SavedConversionConfigDetailResponse:
    try:
        created = workspace.save_conversion_config(
            name=payload.name,
            description=payload.description,
            spec_document=_build_config_document(spec=payload.spec, metadata=payload.metadata),
        )
    except ConversionConfigAlreadyExistsError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return _build_saved_config_detail_response(workspace, created.id)


@router.get("/{config_id}", response_model=SavedConversionConfigDetailResponse)
def get_conversion_config_route(config_id: str, workspace: WorkspaceDep) -> SavedConversionConfigDetailResponse:
    try:
        return _build_saved_config_detail_response(workspace, config_id)
    except ConversionConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{config_id}", response_model=SavedConversionConfigDetailResponse)
def update_conversion_config_route(
    config_id: str,
    payload: SavedConversionConfigUpdateRequest,
    workspace: WorkspaceDep,
) -> SavedConversionConfigDetailResponse:
    try:
        current = workspace.resolve_saved_conversion_config(config_id)
        next_spec = payload.spec if payload.spec is not None else current.document.spec
        next_metadata = payload.metadata if payload.metadata is not None else current.metadata
        updated = workspace.update_saved_conversion_config(
            config_id,
            spec_document=_build_config_document(spec=next_spec, metadata=next_metadata),
            name=payload.name,
            description=payload.description,
        )
    except ConversionConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConversionConfigAlreadyExistsError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return _build_saved_config_detail_response(workspace, updated.id)


@router.post("/{config_id}/duplicate", response_model=SavedConversionConfigDetailResponse, status_code=status.HTTP_201_CREATED)
def duplicate_conversion_config_route(
    config_id: str,
    payload: SavedConversionConfigDuplicateRequest,
    workspace: WorkspaceDep,
) -> SavedConversionConfigDetailResponse:
    try:
        source = workspace.resolve_saved_conversion_config(config_id)
        name = payload.name or _next_duplicate_name(workspace, f"Copy of {source.name}")
        metadata = payload.metadata if payload.metadata is not None else source.metadata
        description = payload.description if payload.description is not None else source.description
        duplicated = workspace.save_conversion_config(
            name=name,
            description=description,
            spec_document=_build_config_document(spec=source.document.spec, metadata=metadata),
        )
    except ConversionConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConversionConfigAlreadyExistsError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return _build_saved_config_detail_response(workspace, duplicated.id)
