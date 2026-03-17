"""Service helpers for creating and attaching asset tags."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db.models import Asset, Tag
from backend.app.services.assets import get_asset_or_raise


class TagServiceError(Exception):
    """Base exception for tag service failures."""


class TagAlreadyExistsError(TagServiceError):
    """Raised when a tag name already exists."""


class TagNotFoundError(TagServiceError):
    """Raised when a tag cannot be found."""


class AssetTagAlreadyExistsError(TagServiceError):
    """Raised when a tag is already attached to an asset."""


class AssetTagNotFoundError(TagServiceError):
    """Raised when a requested asset-tag attachment does not exist."""


def normalize_tag_name(name: str) -> tuple[str, str]:
    display_name = name.strip()
    if not display_name:
        raise ValueError("tag name must be non-empty")
    return display_name, display_name.lower()


def list_tags(session: Session) -> list[Tag]:
    statement = select(Tag).order_by(Tag.normalized_name.asc(), Tag.id.asc())
    return list(session.scalars(statement).all())


def get_tag(session: Session, tag_id: str) -> Tag | None:
    return session.scalar(select(Tag).where(Tag.id == tag_id))


def get_tag_or_raise(session: Session, tag_id: str) -> Tag:
    tag = get_tag(session, tag_id)
    if tag is None:
        raise TagNotFoundError(f"tag not found: {tag_id}")
    return tag


def create_tag(session: Session, *, name: str) -> Tag:
    display_name, normalized_name = normalize_tag_name(name)

    existing_tag = session.scalar(select(Tag).where(Tag.normalized_name == normalized_name))
    if existing_tag is not None:
        raise TagAlreadyExistsError(f"tag already exists: {display_name}")

    tag = Tag(name=display_name, normalized_name=normalized_name)
    session.add(tag)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise TagAlreadyExistsError(f"tag already exists: {display_name}") from exc

    return tag


def attach_tag_to_asset(session: Session, *, asset_id: str, tag_id: str) -> Asset:
    asset = get_asset_or_raise(session, asset_id)
    tag = get_tag_or_raise(session, tag_id)

    if any(existing_tag.id == tag.id for existing_tag in asset.tags):
        raise AssetTagAlreadyExistsError(
            f"tag already attached to asset: {tag.name} -> {asset.file_name}"
        )

    asset.tags.append(tag)
    session.commit()
    return get_asset_or_raise(session, asset_id)


def remove_tag_from_asset(session: Session, *, asset_id: str, tag_id: str) -> Asset:
    asset = get_asset_or_raise(session, asset_id)
    tag = get_tag_or_raise(session, tag_id)

    matching_tag = next((existing_tag for existing_tag in asset.tags if existing_tag.id == tag.id), None)
    if matching_tag is None:
        raise AssetTagNotFoundError(
            f"tag is not attached to asset: {tag.name} -> {asset.file_name}"
        )

    asset.tags.remove(matching_tag)
    session.commit()
    return get_asset_or_raise(session, asset_id)
