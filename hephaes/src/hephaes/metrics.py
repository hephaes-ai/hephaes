from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from .manifest import EpisodeManifest
from .models import BagMetadata, Topic

TopicModality = Literal["image", "points", "scalar_series", "other"]
SensorFamily = Literal["camera", "lidar", "imu", "telemetry", "other"]

VISUAL_MODALITIES: frozenset[TopicModality] = frozenset({"image", "points", "scalar_series"})


@dataclass(frozen=True)
class VisualizationReadinessSummary:
    has_visualizable_streams: bool
    visualizable_stream_count: int


@dataclass(frozen=True)
class BagTopicSummary:
    modality_counts: dict[TopicModality, int]
    sensor_family_counts: dict[SensorFamily, int]
    visualization: VisualizationReadinessSummary


@dataclass(frozen=True)
class DatasetArtifactSummary:
    dataset_format: str
    rows_written: int
    field_count: int
    field_names: list[str]
    source_ros_version: str
    source_storage_format: str


@dataclass(frozen=True)
class ManifestReadinessFlags:
    has_manifest: bool
    has_rows: bool
    has_required_fields: bool


def infer_topic_modality(message_type: str) -> TopicModality:
    modality, _sensor_family = _classify_message_type(message_type)
    return modality


def infer_sensor_family(message_type: str) -> SensorFamily:
    _modality, sensor_family = _classify_message_type(message_type)
    return sensor_family


def summarize_visualization_readiness(topics: Sequence[Topic]) -> VisualizationReadinessSummary:
    visualizable_stream_count = sum(
        1
        for topic in topics
        if infer_topic_modality(topic.message_type) in VISUAL_MODALITIES
    )
    return VisualizationReadinessSummary(
        has_visualizable_streams=visualizable_stream_count > 0,
        visualizable_stream_count=visualizable_stream_count,
    )


def summarize_topics(topics: Sequence[Topic]) -> BagTopicSummary:
    modality_counts: dict[TopicModality, int] = {}
    sensor_family_counts: dict[SensorFamily, int] = {}

    for topic in topics:
        modality = infer_topic_modality(topic.message_type)
        sensor_family = infer_sensor_family(topic.message_type)
        _increment_count(modality_counts, modality)
        _increment_count(sensor_family_counts, sensor_family)

    return BagTopicSummary(
        modality_counts=modality_counts,
        sensor_family_counts=sensor_family_counts,
        visualization=summarize_visualization_readiness(topics),
    )


def summarize_bag_topics(bag_metadata: BagMetadata) -> BagTopicSummary:
    return summarize_topics(bag_metadata.topics)


def summarize_episode_manifest(manifest: EpisodeManifest) -> DatasetArtifactSummary:
    return DatasetArtifactSummary(
        dataset_format=manifest.dataset.format,
        rows_written=manifest.dataset.rows_written,
        field_count=len(manifest.dataset.field_names),
        field_names=list(manifest.dataset.field_names),
        source_ros_version=manifest.source.ros_version,
        source_storage_format=manifest.source.storage_format,
    )


def derive_manifest_readiness_flags(
    manifest: EpisodeManifest | None,
    *,
    required_fields: Sequence[str] | None = None,
) -> ManifestReadinessFlags:
    if manifest is None:
        return ManifestReadinessFlags(
            has_manifest=False,
            has_rows=False,
            has_required_fields=False,
        )

    normalized_required_fields = [field.strip() for field in (required_fields or []) if field.strip()]
    field_names = set(manifest.dataset.field_names)

    return ManifestReadinessFlags(
        has_manifest=True,
        has_rows=manifest.dataset.rows_written > 0,
        has_required_fields=all(field in field_names for field in normalized_required_fields),
    )


def _normalize_message_type(message_type: str) -> str:
    if not isinstance(message_type, str):
        raise TypeError("message_type must be a string")
    return message_type.strip().lower()


def _classify_message_type(message_type: str) -> tuple[TopicModality, SensorFamily]:
    normalized = _normalize_message_type(message_type)

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


def _increment_count(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


__all__ = [
    "BagTopicSummary",
    "DatasetArtifactSummary",
    "ManifestReadinessFlags",
    "SensorFamily",
    "TopicModality",
    "VISUAL_MODALITIES",
    "VisualizationReadinessSummary",
    "derive_manifest_readiness_flags",
    "infer_sensor_family",
    "infer_topic_modality",
    "summarize_bag_topics",
    "summarize_episode_manifest",
    "summarize_topics",
    "summarize_visualization_readiness",
]
