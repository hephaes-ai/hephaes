"""Service helpers for registering and retrieving local assets."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db.models import Asset, Conversion, Job, Tag
from hephaes import Workspace

SUPPORTED_ASSET_FILE_TYPES = {"bag", "mcap"}


class AssetServiceError(Exception):
    """Base exception for asset service failures."""


class InvalidAssetPathError(AssetServiceError):
    """Raised when a requested asset path is invalid or unusable."""


class AssetAlreadyRegisteredError(AssetServiceError):
    """Raised when a file path is already present in the asset registry."""


class AssetDialogUnavailableError(AssetServiceError):
    """Raised when the local environment cannot open a native file picker."""


class AssetNotFoundError(AssetServiceError):
    """Raised when an asset cannot be found in the registry."""


class InvalidAssetUploadError(AssetServiceError):
    """Raised when an uploaded file is invalid or unsupported."""


class InvalidAssetDirectoryError(AssetServiceError):
    """Raised when a directory-scan request points at an invalid location."""


class EpisodeDiscoveryUnavailableError(AssetServiceError):
    """Raised when episode summaries are not available for an asset."""


@dataclass(frozen=True)
class InspectedAssetPath:
    """Normalized local file details used during registration."""

    file_path: str
    file_name: str
    file_type: str
    file_size: int


@dataclass(frozen=True)
class AssetRegistrationSkip:
    """Reason a selected file could not be added to the registry."""

    detail: str
    file_path: str
    reason: str


@dataclass(frozen=True)
class DialogAssetRegistrationResult:
    """Result of opening a native picker and registering selected files."""

    canceled: bool
    registered_assets: list[Asset]
    skipped: list[AssetRegistrationSkip]


@dataclass(frozen=True)
class DirectoryScanResult:
    """Result of scanning a directory and attempting asset registration."""

    discovered_file_count: int
    recursive: bool
    registered_assets: list[Asset]
    scanned_directory: str
    skipped: list[AssetRegistrationSkip]


@dataclass(frozen=True)
class AssetEpisodeSummary:
    """Episode summary derived from indexed asset metadata."""

    default_lane_count: int
    duration: float
    end_time: datetime | None
    episode_id: str
    has_visualizable_streams: bool
    label: str
    start_time: datetime | None


@dataclass(frozen=True)
class AssetListFilters:
    """Normalized filters for listing registered assets."""

    search: str | None = None
    tag: str | None = None
    file_type: str | None = None
    status: str | None = None
    min_duration: float | None = None
    max_duration: float | None = None
    start_after: datetime | None = None
    start_before: datetime | None = None

    @property
    def requires_metadata_join(self) -> bool:
        return any(
            value is not None
            for value in (
                self.min_duration,
                self.max_duration,
                self.start_after,
                self.start_before,
            )
        )

    @property
    def requires_tag_join(self) -> bool:
        return self.tag is not None


TK_FILE_DIALOG_SCRIPT = """
import json
import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()
root.update_idletasks()

try:
    root.attributes("-topmost", True)
except Exception:
    pass

paths = filedialog.askopenfilenames(
    title="Choose asset files",
    filetypes=[
        ("ROS logs", "*.bag *.mcap"),
        ("MCAP files", "*.mcap"),
        ("ROS bag files", "*.bag"),
        ("All files", "*.*"),
    ],
)

print(json.dumps(list(paths)))
root.destroy()
"""

MACOS_FILE_DIALOG_SCRIPT = """
try
    set chosenFiles to choose file with prompt "Choose asset files" of type {"bag", "mcap"} multiple selections allowed true
on error number -128
    return ""
end try

if class of chosenFiles is alias then
    set chosenFiles to {chosenFiles}
end if

set outputLines to {}
repeat with chosenFile in chosenFiles
    set end of outputLines to POSIX path of chosenFile
end repeat

set AppleScript's text item delimiters to linefeed
return outputLines as text
"""


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


def _validate_supported_file_type(file_name: str) -> str:
    file_type = infer_file_type(Path(file_name))
    if file_type not in SUPPORTED_ASSET_FILE_TYPES:
        supported_types = ", ".join(sorted(SUPPORTED_ASSET_FILE_TYPES))
        raise InvalidAssetUploadError(
            f"unsupported asset type: {file_name} (supported: {supported_types})"
        )
    return file_type


def normalize_uploaded_file_name(file_name: str) -> str:
    trimmed = file_name.strip()
    if not trimmed:
        raise InvalidAssetUploadError("uploaded file name must be non-empty")

    normalized_name = Path(trimmed).name
    if normalized_name in {"", ".", ".."}:
        raise InvalidAssetUploadError("uploaded file name is invalid")

    _validate_supported_file_type(normalized_name)
    return normalized_name


def _iter_supported_asset_files(directory: Path, *, recursive: bool) -> Iterable[Path]:
    candidates = directory.rglob("*") if recursive else directory.iterdir()
    for candidate in sorted(candidates):
        if not candidate.is_file():
            continue
        if infer_file_type(candidate) not in SUPPORTED_ASSET_FILE_TYPES:
            continue
        yield candidate


def _parse_dialog_output(stdout: str) -> list[str]:
    return [line.strip() for line in stdout.splitlines() if line.strip()]


def _run_dialog_command(command: list[str], *, input_text: str | None = None) -> list[str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            input=input_text,
            text=True,
        )
    except OSError as exc:
        raise AssetDialogUnavailableError("native file picker could not be started") from exc

    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        message = stderr or "native file picker is unavailable in this environment"
        raise AssetDialogUnavailableError(message)

    return _parse_dialog_output(completed.stdout)


def _open_asset_file_dialog_with_tk() -> list[str]:
    selected_paths = _run_dialog_command(
        [sys.executable, "-c", TK_FILE_DIALOG_SCRIPT],
    )
    if not selected_paths:
        return []

    try:
        parsed_paths = json.loads("\n".join(selected_paths))
    except json.JSONDecodeError as exc:
        raise AssetDialogUnavailableError("native file picker returned an invalid response") from exc

    if not isinstance(parsed_paths, list):
        raise AssetDialogUnavailableError("native file picker returned an unexpected payload")

    return [str(path) for path in parsed_paths if isinstance(path, str) and path.strip()]


def _open_asset_file_dialog_with_osascript() -> list[str]:
    if shutil.which("osascript") is None:
        raise AssetDialogUnavailableError("osascript is not available")

    return _run_dialog_command(
        ["osascript", "-"],
        input_text=MACOS_FILE_DIALOG_SCRIPT,
    )


def open_asset_file_dialog() -> list[str]:
    picker_attempts = []

    if sys.platform == "darwin":
        picker_attempts.append(_open_asset_file_dialog_with_osascript)

    picker_attempts.append(_open_asset_file_dialog_with_tk)

    last_error: AssetDialogUnavailableError | None = None
    for picker_attempt in picker_attempts:
        try:
            return picker_attempt()
        except AssetDialogUnavailableError as exc:
            last_error = exc

    raise last_error or AssetDialogUnavailableError(
        "native file picker is unavailable in this environment"
    )


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


def register_assets_from_dialog(session: Session) -> DialogAssetRegistrationResult:
    selected_paths = open_asset_file_dialog()
    if not selected_paths:
        return DialogAssetRegistrationResult(
            canceled=True,
            registered_assets=[],
            skipped=[],
        )

    registered_assets: list[Asset] = []
    skipped: list[AssetRegistrationSkip] = []

    for file_path in selected_paths:
        try:
            asset = register_asset(session, file_path=file_path)
        except InvalidAssetPathError as exc:
            skipped.append(
                AssetRegistrationSkip(
                    detail=str(exc),
                    file_path=file_path,
                    reason="invalid_path",
                )
            )
        except AssetAlreadyRegisteredError as exc:
            skipped.append(
                AssetRegistrationSkip(
                    detail=str(exc),
                    file_path=file_path,
                    reason="duplicate",
                )
            )
        else:
            registered_assets.append(asset)

    return DialogAssetRegistrationResult(
        canceled=False,
        registered_assets=registered_assets,
        skipped=skipped,
    )


def upload_asset(
    session: Session,
    *,
    content: bytes,
    file_name: str,
) -> Asset:
    normalized_file_name = normalize_uploaded_file_name(file_name)

    if not content:
        raise InvalidAssetUploadError("uploaded file is empty")

    settings = get_settings()
    settings.raw_data_dir.mkdir(parents=True, exist_ok=True)

    target_path = settings.raw_data_dir / normalized_file_name
    if target_path.exists():
        raise AssetAlreadyRegisteredError(f"asset already registered: {target_path}")

    target_path.write_bytes(content)

    try:
        return register_asset(session, file_path=str(target_path))
    except Exception:
        target_path.unlink(missing_ok=True)
        raise


def scan_directory_for_assets(
    session: Session,
    *,
    directory_path: str,
    recursive: bool = True,
) -> DirectoryScanResult:
    normalized_directory = normalize_asset_path(directory_path)
    if not normalized_directory.exists():
        raise InvalidAssetDirectoryError(f"asset directory does not exist: {normalized_directory}")
    if not normalized_directory.is_dir():
        raise InvalidAssetDirectoryError(f"asset directory is not a directory: {normalized_directory}")

    discovered_paths = list(_iter_supported_asset_files(normalized_directory, recursive=recursive))
    registered_assets: list[Asset] = []
    skipped: list[AssetRegistrationSkip] = []

    for discovered_path in discovered_paths:
        try:
            asset = register_asset(session, file_path=str(discovered_path))
        except InvalidAssetPathError as exc:
            skipped.append(
                AssetRegistrationSkip(
                    detail=str(exc),
                    file_path=str(discovered_path),
                    reason="invalid_path",
                )
            )
        except AssetAlreadyRegisteredError as exc:
            skipped.append(
                AssetRegistrationSkip(
                    detail=str(exc),
                    file_path=str(discovered_path),
                    reason="duplicate",
                )
            )
        else:
            registered_assets.append(asset)

    return DirectoryScanResult(
        discovered_file_count=len(discovered_paths),
        recursive=recursive,
        registered_assets=registered_assets,
        scanned_directory=str(normalized_directory),
        skipped=skipped,
    )


def list_assets(session: Session, *, filters: AssetListFilters | None = None) -> list[Asset]:
    filters = filters or AssetListFilters()
    statement = select(Asset).options(selectinload(Asset.tags))

    if filters.requires_metadata_join:
        statement = statement.outerjoin(AssetMetadata, AssetMetadata.asset_id == Asset.id)
    if filters.requires_tag_join:
        statement = statement.join(Asset.tags)

    if filters.search is not None:
        statement = statement.where(func.lower(Asset.file_name).contains(filters.search.lower()))
    if filters.tag is not None:
        statement = statement.where(Tag.normalized_name == filters.tag.lower())
    if filters.file_type is not None:
        statement = statement.where(func.lower(Asset.file_type) == filters.file_type.lower())
    if filters.status is not None:
        statement = statement.where(Asset.indexing_status == filters.status)
    if filters.min_duration is not None:
        statement = statement.where(AssetMetadata.duration >= filters.min_duration)
    if filters.max_duration is not None:
        statement = statement.where(AssetMetadata.duration <= filters.max_duration)
    if filters.start_after is not None:
        statement = statement.where(AssetMetadata.start_time >= filters.start_after)
    if filters.start_before is not None:
        statement = statement.where(AssetMetadata.start_time <= filters.start_before)

    statement = statement.order_by(Asset.registered_time.desc(), Asset.id.desc())
    return list(session.scalars(statement).unique().all())


def get_asset(session: Session, asset_id: str) -> Asset | None:
    statement = (
        select(Asset)
        .options(
            selectinload(Asset.metadata_record),
            selectinload(Asset.tags),
        )
        .where(Asset.id == asset_id)
    )
    asset = session.scalar(statement)
    if asset is not None:
        return asset

    workspace = Workspace.open(get_settings().workspace_root)
    workspace_asset = workspace.get_asset(asset_id)
    if workspace_asset is None:
        return None

    workspace_metadata = workspace.get_asset_metadata(asset_id)
    metadata_record = None
    if workspace_metadata is not None:
        metadata_record = SimpleNamespace(
            duration=workspace_metadata.duration,
            start_time=workspace_metadata.start_time,
            end_time=workspace_metadata.end_time,
            topic_count=workspace_metadata.topic_count,
            message_count=workspace_metadata.message_count,
            sensor_types_json=[str(sensor_type) for sensor_type in workspace_metadata.sensor_types],
            topics_json=[
                {
                    "name": topic.name,
                    "message_type": topic.message_type,
                    "message_count": topic.message_count,
                    "rate_hz": topic.rate_hz,
                    "modality": topic.modality,
                }
                for topic in workspace_metadata.topics
            ],
            default_episode_json=(
                {
                    "episode_id": workspace_metadata.default_episode.episode_id,
                    "label": workspace_metadata.default_episode.label,
                    "duration": workspace_metadata.default_episode.duration,
                }
                if workspace_metadata.default_episode is not None
                else None
            ),
            visualization_summary_json=(
                {
                    "has_visualizable_streams": workspace_metadata.visualization_summary.has_visualizable_streams,
                    "default_lane_count": workspace_metadata.visualization_summary.default_lane_count,
                }
                if workspace_metadata.visualization_summary is not None
                else None
            ),
            raw_metadata_json=(
                {
                    "compression_format": workspace_metadata.raw_metadata.compression_format,
                    "file_path": workspace_metadata.raw_metadata.file_path,
                    "file_size_bytes": workspace_metadata.raw_metadata.file_size_bytes,
                    "path": workspace_metadata.raw_metadata.path,
                    "ros_version": workspace_metadata.raw_metadata.ros_version,
                    "storage_format": workspace_metadata.raw_metadata.storage_format,
                }
                if workspace_metadata.raw_metadata is not None
                else None
            ),
            indexing_error=workspace_metadata.indexing_error,
        )

    return SimpleNamespace(
        id=workspace_asset.id,
        file_path=workspace_asset.file_path,
        file_name=workspace_asset.file_name,
        file_type=workspace_asset.file_type,
        file_size=workspace_asset.file_size,
        indexing_status=workspace_asset.indexing_status,
        last_indexed_time=workspace_asset.last_indexed_at,
        registered_time=workspace_asset.registered_at,
        metadata_record=metadata_record,
        tags=workspace.get_asset_tags(workspace_asset.id),
    )


def get_asset_or_raise(session: Session, asset_id: str) -> Asset:
    asset = get_asset(session, asset_id)
    if asset is None:
        raise AssetNotFoundError(f"asset not found: {asset_id}")
    return asset


def list_asset_episodes(asset: Asset) -> list[AssetEpisodeSummary]:
    metadata_record = asset.metadata_record
    if metadata_record is None or metadata_record.default_episode_json is None:
        raise EpisodeDiscoveryUnavailableError(
            f"asset must be indexed before episodes are available: {asset.file_name}"
        )

    default_episode = metadata_record.default_episode_json
    visualization_summary = metadata_record.visualization_summary_json or {}

    return [
        AssetEpisodeSummary(
            default_lane_count=int(visualization_summary.get("default_lane_count", 0)),
            duration=float(default_episode["duration"]),
            end_time=metadata_record.end_time,
            episode_id=str(default_episode["episode_id"]),
            has_visualizable_streams=bool(
                visualization_summary.get("has_visualizable_streams", False)
            ),
            label=str(default_episode["label"]),
            start_time=metadata_record.start_time,
        )
    ]


def list_related_jobs_for_asset(
    session: Session,
    *,
    asset_id: str,
    limit: int = 10,
) -> list[Job]:
    statement = select(Job).order_by(Job.created_at.desc(), Job.id.desc())
    jobs = [job for job in session.scalars(statement).all() if asset_id in job.target_asset_ids_json]
    return jobs[:limit]


def list_related_conversions_for_asset(
    session: Session,
    *,
    asset_id: str,
    limit: int = 10,
) -> list[Conversion]:
    statement = select(Conversion).order_by(Conversion.created_at.desc(), Conversion.id.desc())
    conversions = [
        conversion
        for conversion in session.scalars(statement).all()
        if asset_id in conversion.source_asset_ids_json
    ]
    return conversions[:limit]
