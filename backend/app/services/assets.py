"""Service helpers for registering and retrieving local assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db.models import Asset


class AssetServiceError(Exception):
    """Base exception for asset service failures."""


class InvalidAssetPathError(AssetServiceError):
    """Raised when a requested asset path is invalid or unusable."""


class AssetAlreadyRegisteredError(AssetServiceError):
    """Raised when a file path is already present in the asset registry."""


class AssetNotFoundError(AssetServiceError):
    """Raised when an asset cannot be found in the registry."""


@dataclass(frozen=True)
class InspectedAssetPath:
    """Normalized local file details used during registration."""

    file_path: str
    file_name: str
    file_type: str
    file_size: int


def normalize_asset_path(file_path: str) -> Path:
    path = Path(file_path).expanduser()
    if not path.is_absolute():
        path = path.resolve(strict=False)
    else:
        path = path.resolve(strict=False)
    return path


def inspect_asset_path(file_path: str) -> InspectedAssetPath:
    path = normalize_asset_path(file_path)

    if not path.exists():
        raise InvalidAssetPathError(f"asset path does not exist: {path}")
    if not path.is_file():
        raise InvalidAssetPathError(f"asset path is not a file: {path}")

    stat_result = path.stat()
    return InspectedAssetPath(
        file_path=str(path),
        file_name=path.name,
        file_type=infer_file_type(path),
        file_size=stat_result.st_size,
    )


def infer_file_type(path: Path) -> str:
    suffix = path.suffix.strip().lower()
    if suffix.startswith("."):
        suffix = suffix[1:]
    return suffix or "unknown"


def register_asset(session: Session, *, file_path: str) -> Asset:
    inspected = inspect_asset_path(file_path)

    existing_asset = session.scalar(
        select(Asset).where(Asset.file_path == inspected.file_path),
    )
    if existing_asset is not None:
        raise AssetAlreadyRegisteredError(f"asset already registered: {inspected.file_path}")

    asset = Asset(
        file_path=inspected.file_path,
        file_name=inspected.file_name,
        file_type=inspected.file_type,
        file_size=inspected.file_size,
        indexing_status="pending",
    )
    session.add(asset)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise AssetAlreadyRegisteredError(f"asset already registered: {inspected.file_path}") from exc

    session.refresh(asset)
    return asset


def list_assets(session: Session) -> list[Asset]:
    statement = select(Asset).order_by(Asset.registered_time.desc(), Asset.id.desc())
    return list(session.scalars(statement).all())


def get_asset(session: Session, asset_id: str) -> Asset | None:
    return session.get(Asset, asset_id)


def get_asset_or_raise(session: Session, asset_id: str) -> Asset:
    asset = get_asset(session, asset_id)
    if asset is None:
        raise AssetNotFoundError(f"asset not found: {asset_id}")
    return asset
