"""Indexing service for extracting and persisting asset metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from hephaes import Profiler
from hephaes.models import BagMetadata

from backend.app.db.models import Asset, AssetMetadata, utc_now
from backend.app.services.assets import AssetNotFoundError, get_asset_or_raise

VISUAL_MODALITIES = {"image", "points", "scalar_series"}


class AssetIndexingError(Exception):
    """Raised when metadata extraction fails for a registered asset."""


@dataclass(frozen=True)
class ReindexAllResult:
    failed_assets: list[Asset]
    indexed_assets: list[Asset]


def profile_asset_file(file_path: str) -> BagMetadata:
    """Profile a single asset file through the reusable hephaes package."""

    return Profiler([file_path], max_workers=1).profile()[0]


def _topic_modality(message_type: str) -> tuple[str, str]:
    normalized = message_type.lower()

    if "image" in normalized:
        return "image", "camera"
    if any(token in normalized for token in ("pointcloud", "point_cloud", "laser", "scan")):
        return "points", "lidar"
    if "imu" in normalized:
        return "scalar_series", "imu"
    if any(
        token in normalized
        for token in (
            "odometry",
            "twist",
            "pose",
            "jointstate",
            "joint_state",
            "navsatfix",
            "gps",
            "temperature",
            "battery",
            "magneticfield",
            "fluidpressure",
        )
    ):
        return "scalar_series", "telemetry"
    return "other", "other"


def _timestamp_ns_to_datetime(timestamp_ns: int | None) -> datetime | None:
    if timestamp_ns is None:
        return None

    return datetime.fromtimestamp(timestamp_ns / 1e9, tz=UTC)


def _build_metadata_payload(asset: Asset, profile: BagMetadata) -> dict[str, object]:
    topics_payload: list[dict[str, object]] = []
    sensor_types: list[str] = []

    for topic in profile.topics:
        modality, sensor_type = _topic_modality(topic.message_type)
        topics_payload.append(
            {
                "name": topic.name,
                "message_type": topic.message_type,
                "message_count": topic.message_count,
                "rate_hz": topic.rate_hz,
                "modality": modality,
            }
        )
        if sensor_type != "other" and sensor_type not in sensor_types:
            sensor_types.append(sensor_type)

    if not sensor_types and topics_payload:
        sensor_types = ["other"]

    visualizable_topic_count = sum(
        1 for topic in topics_payload if str(topic["modality"]) in VISUAL_MODALITIES
    )

    return {
        "duration": profile.duration_seconds,
        "end_time": _timestamp_ns_to_datetime(profile.end_timestamp),
        "message_count": profile.message_count,
        "raw_metadata_json": {
            "compression_format": profile.compression_format,
            "file_path": profile.file_path,
            "file_size_bytes": profile.file_size_bytes,
            "path": profile.path,
            "ros_version": profile.ros_version,
            "storage_format": profile.storage_format,
        },
        "sensor_types_json": sensor_types,
        "start_time": _timestamp_ns_to_datetime(profile.start_timestamp),
        "topic_count": len(topics_payload),
        "topics_json": topics_payload,
        "default_episode_json": {
            "episode_id": f"{asset.id}:default",
            "label": "Episode 1",
            "duration": profile.duration_seconds,
        },
        "visualization_summary_json": {
            "has_visualizable_streams": visualizable_topic_count > 0,
            "default_lane_count": visualizable_topic_count,
        },
    }


def _upsert_metadata_record(
    session: Session,
    *,
    asset: Asset,
    payload: dict[str, object] | None = None,
    indexing_error: str | None = None,
) -> AssetMetadata:
    metadata_record = asset.metadata_record
    if metadata_record is None:
        metadata_record = AssetMetadata(asset_id=asset.id)
        asset.metadata_record = metadata_record
        session.add(metadata_record)

    if payload:
        metadata_record.duration = payload["duration"]  # type: ignore[assignment]
        metadata_record.start_time = payload["start_time"]  # type: ignore[assignment]
        metadata_record.end_time = payload["end_time"]  # type: ignore[assignment]
        metadata_record.topic_count = payload["topic_count"]  # type: ignore[assignment]
        metadata_record.message_count = payload["message_count"]  # type: ignore[assignment]
        metadata_record.sensor_types_json = payload["sensor_types_json"]  # type: ignore[assignment]
        metadata_record.topics_json = payload["topics_json"]  # type: ignore[assignment]
        metadata_record.default_episode_json = payload["default_episode_json"]  # type: ignore[assignment]
        metadata_record.visualization_summary_json = payload["visualization_summary_json"]  # type: ignore[assignment]
        metadata_record.raw_metadata_json = payload["raw_metadata_json"]  # type: ignore[assignment]

    metadata_record.indexing_error = indexing_error
    metadata_record.updated_at = utc_now()
    return metadata_record


class IndexingService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def index_asset(self, asset_id: str) -> Asset:
        asset = get_asset_or_raise(self.session, asset_id)
        asset.indexing_status = "indexing"
        self.session.commit()

        try:
            profile = profile_asset_file(asset.file_path)
            payload = _build_metadata_payload(asset, profile)
            _upsert_metadata_record(self.session, asset=asset, payload=payload, indexing_error=None)
            asset.indexing_status = "indexed"
            asset.last_indexed_time = utc_now()
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            failed_asset = get_asset_or_raise(self.session, asset_id)
            _upsert_metadata_record(
                self.session,
                asset=failed_asset,
                indexing_error=str(exc),
            )
            failed_asset.indexing_status = "failed"
            self.session.commit()
            raise AssetIndexingError(str(exc)) from exc

        return get_asset_or_raise(self.session, asset_id)

    def reindex_all_pending_assets(self) -> ReindexAllResult:
        statement = (
            select(Asset)
            .where(
                or_(
                    Asset.indexing_status.in_(("pending", "failed")),
                    Asset.last_indexed_time.is_(None),
                )
            )
            .order_by(Asset.registered_time.asc(), Asset.id.asc())
        )
        assets = list(self.session.scalars(statement).all())

        indexed_assets: list[Asset] = []
        failed_assets: list[Asset] = []

        for asset in assets:
            try:
                indexed_assets.append(self.index_asset(asset.id))
            except (AssetIndexingError, AssetNotFoundError):
                failed_assets.append(get_asset_or_raise(self.session, asset.id))

        return ReindexAllResult(
            failed_assets=failed_assets,
            indexed_assets=indexed_assets,
        )
