"""Service helpers for Rerun visualization preparation and viewer-source manifests."""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy.orm.session import sessionmaker

from hephaes import Workspace
from hephaes._converter_helpers import _normalize_payload

from app.config import get_settings
from app.db.models import Job
from app.services.assets import AssetNotFoundError
from app.services.episodes import (
    get_episode_detail,
    open_asset_reader,
)
from app.services.jobs import JobService, find_latest_job_for_target

logger = logging.getLogger(__name__)

# Pinned Rerun SDK version used for recording generation.
# Bump intentionally when upgrading the rerun-sdk dependency.
RERUN_SDK_VERSION = "0.22"
RERUN_RECORDING_FORMAT_VERSION = "1"


class VisualizationError(Exception):
    """Base exception for visualization service failures."""


class VisualizationNotFoundError(VisualizationError):
    """Raised when a viewer source or artifact cannot be found."""


class VisualizationGenerationError(VisualizationError):
    """Raised when RRD recording generation fails."""


@dataclass(frozen=True)
class ViewerSourceManifest:
    """Lightweight manifest the frontend uses to load the official Rerun viewer."""

    episode_id: str
    status: str
    source_kind: str | None = None
    source_url: str | None = None
    job_id: str | None = None
    artifact_path: str | None = None
    error_message: str | None = None
    viewer_version: str | None = None
    recording_version: str | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class VisualizationArtifactMetadata:
    """Sidecar metadata used to validate cached viewer artifacts."""

    asset_id: str
    episode_id: str
    viewer_version: str
    recording_version: str
    generated_at: datetime


@dataclass(frozen=True)
class PendingVisualizationExecution:
    job_id: str
    asset_id: str
    asset_file_path: str
    episode_id: str
    topics: list[str]
    output_path: Path
    viewer_version: str
    recording_version: str


def _artifact_output_dir(asset_id: str, episode_id: str) -> Path:
    settings = get_settings()
    return settings.outputs_dir / "visualizations" / asset_id / episode_id


def _artifact_file_path(asset_id: str, episode_id: str) -> Path:
    return _artifact_output_dir(asset_id, episode_id) / "recording.rrd"


def _artifact_metadata_path(asset_id: str, episode_id: str) -> Path:
    return _artifact_output_dir(asset_id, episode_id) / "recording.meta.json"


def _find_cached_artifact(asset_id: str, episode_id: str) -> Path | None:
    rrd_path = _artifact_file_path(asset_id, episode_id)
    if rrd_path.exists() and rrd_path.stat().st_size > 0:
        return rrd_path
    return None


def _source_url_for_artifact(asset_id: str, episode_id: str) -> str:
    return f"/visualizations/{asset_id}/{episode_id}/recording.rrd"


def _normalize_utc_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _write_artifact_metadata(
    asset_id: str,
    episode_id: str,
    *,
    viewer_version: str,
    recording_version: str,
) -> VisualizationArtifactMetadata:
    metadata = VisualizationArtifactMetadata(
        asset_id=asset_id,
        episode_id=episode_id,
        viewer_version=viewer_version,
        recording_version=recording_version,
        generated_at=datetime.now(UTC),
    )
    metadata_path = _artifact_metadata_path(asset_id, episode_id)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(
            {
                "asset_id": metadata.asset_id,
                "episode_id": metadata.episode_id,
                "viewer_version": metadata.viewer_version,
                "recording_version": metadata.recording_version,
                "generated_at": metadata.generated_at.isoformat().replace("+00:00", "Z"),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return metadata


def _read_artifact_metadata(asset_id: str, episode_id: str) -> VisualizationArtifactMetadata | None:
    metadata_path = _artifact_metadata_path(asset_id, episode_id)
    if not metadata_path.exists():
        return None

    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    try:
        return VisualizationArtifactMetadata(
            asset_id=str(payload["asset_id"]),
            episode_id=str(payload["episode_id"]),
            viewer_version=str(payload["viewer_version"]),
            recording_version=str(payload["recording_version"]),
            generated_at=_normalize_utc_datetime(payload["generated_at"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _invalidate_cached_artifact(asset_id: str, episode_id: str) -> None:
    for path in (
        _artifact_file_path(asset_id, episode_id),
        _artifact_metadata_path(asset_id, episode_id),
    ):
        path.unlink(missing_ok=True)


def _resolve_cached_artifact(
    asset_id: str,
    episode_id: str,
    *,
    viewer_version: str,
    recording_version: str,
) -> tuple[Path, VisualizationArtifactMetadata] | tuple[None, None]:
    artifact_path = _find_cached_artifact(asset_id, episode_id)
    metadata = _read_artifact_metadata(asset_id, episode_id)

    if artifact_path is None or metadata is None:
        if artifact_path is not None or metadata is not None:
            _invalidate_cached_artifact(asset_id, episode_id)
        return None, None

    if (
        metadata.asset_id != asset_id
        or metadata.episode_id != episode_id
        or metadata.viewer_version != viewer_version
        or metadata.recording_version != recording_version
    ):
        _invalidate_cached_artifact(asset_id, episode_id)
        return None, None

    return artifact_path, metadata


def _decode_normalized_bytes(payload: object) -> bytes | None:
    if isinstance(payload, (bytes, bytearray)):
        return bytes(payload)

    if not isinstance(payload, dict):
        return None

    if payload.get("__bytes__") is not True:
        return None
    if payload.get("encoding") != "base64":
        return None

    encoded_value = payload.get("value")
    if not isinstance(encoded_value, str):
        return None

    try:
        return base64.b64decode(encoded_value)
    except Exception:
        return None


def _generate_rrd(
    asset_file_path: str,
    *,
    asset_id: str,
    episode_id: str,
    topics: list[str],
    output_path: Path,
) -> Path:
    """Read episode streams and write a Rerun .rrd recording."""
    try:
        import rerun as rr
    except ModuleNotFoundError as exc:
        raise VisualizationGenerationError(
            "rerun-sdk is not installed in the backend environment. "
            "Install backend extras with: pip install -e '.[backend]'"
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)

    rr.init(f"hephaes/{episode_id}", spawn=False)
    stream = rr.binary_stream()

    try:
        with open_asset_reader(asset_file_path) as reader:
            for message in reader.read_messages(topics=topics):
                payload = _normalize_payload(message.data)
                rr.set_time_nanos("timestamp", message.timestamp)

                if isinstance(payload, dict) and "width" in payload and "height" in payload:
                    image_bytes = _decode_normalized_bytes(payload.get("data"))
                    if image_bytes is not None:
                        rr.log(
                            message.topic,
                            rr.Image(
                                bytes=image_bytes,
                                width=payload["width"],
                                height=payload["height"],
                                pixel_format=rr.PixelFormat.NV12
                                if payload.get("encoding") == "nv12"
                                else None,
                            ),
                        )
                    else:
                        rr.log(message.topic, rr.TextLog(str(payload)))
                elif isinstance(payload, dict) and "points" in payload:
                    points = payload["points"]
                    if isinstance(points, list) and points:
                        positions = [[p.get("x", 0), p.get("y", 0), p.get("z", 0)] for p in points]
                        rr.log(message.topic, rr.Points3D(positions))
                    else:
                        rr.log(message.topic, rr.TextLog(str(payload)))
                else:
                    rr.log(message.topic, rr.TextLog(str(payload)))
    except Exception as exc:
        raise VisualizationGenerationError(
            f"failed to generate RRD recording for episode {episode_id}: {exc}"
        ) from exc

    output_path.write_bytes(stream.read(flush=True))

    return output_path


class VisualizationService:
    def __init__(self, session: Session, workspace: Workspace) -> None:
        self.session = session
        self.workspace = workspace
        self.job_service = JobService(session)
        self.settings = get_settings()

    def prepare_visualization_job(
        self,
        asset_id: str,
        episode_id: str,
    ) -> tuple[Job, PendingVisualizationExecution | None]:
        """Create or reuse a prepare_visualization job for the given episode."""
        asset = self.workspace.get_asset(asset_id)
        if asset is None:
            raise AssetNotFoundError(f"asset not found: {asset_id}")
        detail = get_episode_detail(self.workspace, asset_id, episode_id)
        viewer_version = self.settings.rerun_sdk_version
        recording_version = self.settings.rerun_recording_format_version

        existing_job = find_latest_job_for_target(
            self.session,
            job_type="prepare_visualization",
            target_asset_id=asset_id,
            episode_id=episode_id,
        )
        cached_artifact, _cached_metadata = _resolve_cached_artifact(
            asset_id,
            episode_id,
            viewer_version=viewer_version,
            recording_version=recording_version,
        )

        if existing_job is not None:
            if existing_job.status in {"queued", "running"}:
                return existing_job, None
            if existing_job.status == "succeeded" and cached_artifact is not None:
                return existing_job, None

        topics = [stream.source_topic for stream in detail.streams]
        output_path = _artifact_file_path(asset_id, episode_id)

        job = self.job_service.create_job(
            job_type="prepare_visualization",
            target_asset_ids=[asset_id],
            config={"episode_id": episode_id},
            output_path=str(output_path),
        )

        return (
            job,
            PendingVisualizationExecution(
                job_id=job.id,
                asset_id=asset_id,
                asset_file_path=asset.file_path,
                episode_id=episode_id,
                topics=topics,
                output_path=output_path,
                viewer_version=viewer_version,
                recording_version=recording_version,
            ),
        )

    def execute_visualization_job(self, execution: PendingVisualizationExecution) -> Job:
        self.job_service.mark_job_running(execution.job_id)
        try:
            _generate_rrd(
                execution.asset_file_path,
                asset_id=execution.asset_id,
                episode_id=execution.episode_id,
                topics=execution.topics,
                output_path=execution.output_path,
            )
            _write_artifact_metadata(
                execution.asset_id,
                execution.episode_id,
                viewer_version=execution.viewer_version,
                recording_version=execution.recording_version,
            )
            return self.job_service.mark_job_succeeded(
                execution.job_id,
                output_path=str(execution.output_path),
            )
        except Exception as exc:
            self.session.rollback()
            _invalidate_cached_artifact(execution.asset_id, execution.episode_id)
            self.job_service.mark_job_failed(execution.job_id, error_message=str(exc))
            raise VisualizationGenerationError(str(exc)) from exc

    def prepare_visualization(self, asset_id: str, episode_id: str) -> Job:
        job, execution = self.prepare_visualization_job(asset_id, episode_id)
        if execution is None:
            return job
        return self.execute_visualization_job(execution)

    def get_viewer_source(self, asset_id: str, episode_id: str) -> ViewerSourceManifest:
        """Return the current viewer-source manifest for an episode."""
        get_episode_detail(self.workspace, asset_id, episode_id)
        viewer_version = self.settings.rerun_sdk_version
        recording_version = self.settings.rerun_recording_format_version

        job = find_latest_job_for_target(
            self.session,
            job_type="prepare_visualization",
            target_asset_id=asset_id,
            episode_id=episode_id,
        )
        cached_artifact, artifact_metadata = _resolve_cached_artifact(
            asset_id,
            episode_id,
            viewer_version=viewer_version,
            recording_version=recording_version,
        )

        if cached_artifact is not None and artifact_metadata is not None:
            return ViewerSourceManifest(
                episode_id=episode_id,
                status="ready",
                source_kind="rrd_url",
                source_url=_source_url_for_artifact(asset_id, episode_id),
                job_id=job.id if job is not None else None,
                artifact_path=str(cached_artifact),
                viewer_version=artifact_metadata.viewer_version,
                recording_version=artifact_metadata.recording_version,
                updated_at=artifact_metadata.generated_at,
            )

        if job is None:
            return ViewerSourceManifest(episode_id=episode_id, status="none")

        if job.status in {"queued", "running"}:
            return ViewerSourceManifest(
                episode_id=episode_id,
                status="preparing",
                job_id=job.id,
                updated_at=job.updated_at,
            )

        if job.status == "failed":
            return ViewerSourceManifest(
                episode_id=episode_id,
                status="failed",
                job_id=job.id,
                error_message=job.error_message,
                updated_at=job.updated_at,
            )

        if cached_artifact is None or artifact_metadata is None:
            return ViewerSourceManifest(
                episode_id=episode_id,
                status="none",
                job_id=job.id,
                error_message=(
                    "Prepared visualization artifact is missing or incompatible with the current "
                    "Rerun version. Re-run visualization preparation."
                ),
                updated_at=job.updated_at,
            )

        return ViewerSourceManifest(
            episode_id=episode_id,
            status="ready",
            source_kind="rrd_url",
            source_url=_source_url_for_artifact(asset_id, episode_id),
            job_id=job.id,
            artifact_path=str(cached_artifact),
            viewer_version=artifact_metadata.viewer_version,
            recording_version=artifact_metadata.recording_version,
            updated_at=artifact_metadata.generated_at,
        )


def run_visualization_job_in_background(
    session_factory: sessionmaker[Session],
    *,
    execution: PendingVisualizationExecution,
) -> None:
    session = session_factory()
    try:
        VisualizationService(session, Workspace.open(get_settings().workspace_root)).execute_visualization_job(
            execution
        )
    finally:
        session.close()
