"""Tag routes for the backend application."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_workspace
from app.mappers.workspace import map_tag_catalog_response
from app.schemas.assets import TagCatalogResponse, TagCreateRequest
from hephaes import TagAlreadyExistsError, Workspace

router = APIRouter(prefix="/tags", tags=["tags"])
WorkspaceDep = Annotated[Workspace, Depends(get_workspace)]


@router.get("", response_model=list[TagCatalogResponse])
def list_tags_route(workspace: WorkspaceDep) -> list[TagCatalogResponse]:
    assets = workspace.list_assets()
    asset_counts: dict[str, int] = {}
    for asset in assets:
        for tag in workspace.get_asset_tags(asset.id):
            asset_counts[tag.id] = asset_counts.get(tag.id, 0) + 1
    return [
        map_tag_catalog_response(tag, asset_count=asset_counts.get(tag.id, 0))
        for tag in workspace.list_tags()
    ]


@router.post("", response_model=TagCatalogResponse, status_code=status.HTTP_201_CREATED)
def create_tag_route(payload: TagCreateRequest, workspace: WorkspaceDep) -> TagCatalogResponse:
    try:
        tag = workspace.create_tag(payload.name)
    except TagAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return map_tag_catalog_response(tag, asset_count=0)
