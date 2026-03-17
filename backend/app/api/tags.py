"""Tag routes for the backend application."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db_session
from backend.app.schemas.assets import TagCatalogResponse, TagCreateRequest
from backend.app.services.tags import TagAlreadyExistsError, create_tag, list_tags

router = APIRouter(prefix="/tags", tags=["tags"])
DbSession = Annotated[Session, Depends(get_db_session)]


@router.get("", response_model=list[TagCatalogResponse])
def list_tags_route(session: DbSession) -> list[TagCatalogResponse]:
    tags = list_tags(session)
    return [
        TagCatalogResponse(
            id=tag.id,
            name=tag.name,
            created_at=tag.created_at,
            asset_count=len(tag.assets),
        )
        for tag in tags
    ]


@router.post("", response_model=TagCatalogResponse, status_code=status.HTTP_201_CREATED)
def create_tag_route(payload: TagCreateRequest, session: DbSession) -> TagCatalogResponse:
    try:
        tag = create_tag(session, name=payload.name)
    except TagAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return TagCatalogResponse(
        id=tag.id,
        name=tag.name,
        created_at=tag.created_at,
        asset_count=0,
    )
