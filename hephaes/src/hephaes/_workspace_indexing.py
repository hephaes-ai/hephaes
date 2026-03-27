from __future__ import annotations

from datetime import UTC, datetime

from ._workspace_models import (
    DefaultEpisodeSummary,
    IndexedTopicSummary,
    IndexMetadataPayload,
    RegisteredAsset,
    SourceAssetMetadata,
    VisualizationSummary,
)
from .metrics import infer_topic_modality, summarize_bag_topics
from .models import BagMetadata
from .profiler import Profiler


def profile_asset_file(file_path: str, *, max_workers: int = 1) -> BagMetadata:
    return Profiler([file_path], max_workers=max_workers).profile()[0]


def build_index_metadata_payload(
    asset: RegisteredAsset,
    profile: BagMetadata,
) -> IndexMetadataPayload:
    topic_summary = summarize_bag_topics(profile)
    topics = [
        IndexedTopicSummary(
            name=topic.name,
            message_type=topic.message_type,
            message_count=topic.message_count,
            rate_hz=topic.rate_hz,
            modality=infer_topic_modality(topic.message_type),
        )
        for topic in profile.topics
    ]

    sensor_types = [
        sensor_family
        for sensor_family in topic_summary.sensor_family_counts
        if sensor_family != "other"
    ]
    if not sensor_types and topics:
        sensor_types = ["other"]

    return IndexMetadataPayload(
        duration=profile.duration_seconds,
        start_time=_timestamp_ns_to_datetime(profile.start_timestamp),
        end_time=_timestamp_ns_to_datetime(profile.end_timestamp),
        topic_count=len(topics),
        message_count=profile.message_count,
        sensor_types=sensor_types,
        topics=topics,
        default_episode=DefaultEpisodeSummary(
            episode_id=f"{asset.id}:default",
            label="Episode 1",
            duration=profile.duration_seconds,
        ),
        visualization_summary=VisualizationSummary(
            has_visualizable_streams=topic_summary.visualization.has_visualizable_streams,
            default_lane_count=topic_summary.visualization.visualizable_stream_count,
        ),
        raw_metadata=SourceAssetMetadata(
            compression_format=profile.compression_format,
            file_path=profile.file_path,
            file_size_bytes=profile.file_size_bytes,
            path=profile.path,
            ros_version=profile.ros_version,
            storage_format=profile.storage_format,
        ),
    )


def _timestamp_ns_to_datetime(timestamp_ns: int | None) -> datetime | None:
    if timestamp_ns is None:
        return None
    return datetime.fromtimestamp(timestamp_ns / 1e9, tz=UTC)
