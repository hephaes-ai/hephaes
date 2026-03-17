"""Tag routes for the backend application."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db_session
from backend.app.schemas.assets import TagCreateRequest, TagResponse
from backend.app.services.tags import TagAlreadyExistsError, create_tag, list_tags

router = APIRouter(prefix="/tags", tags=["tags"])
DbSession = Annotated[Session, Depends(get_db_session)]


@router.get("", response_model=list[TagResponse])
def list_tags_route(session: DbSession) -> list[TagResponse]:
    tags = list_tags(session)
    return [TagResponse.model_validate(tag) for tag in tags]


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
def create_tag_route(payload: TagCreateRequest, session: DbSession) -> TagResponse:
    try:
        tag = create_tag(session, name=payload.name)
    except TagAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return TagResponse.model_validate(tag)
