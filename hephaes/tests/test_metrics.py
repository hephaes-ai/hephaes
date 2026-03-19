from __future__ import annotations

from hephaes.manifest import EpisodeManifest
from hephaes.metrics import (
    VISUAL_MODALITIES,
    derive_manifest_readiness_flags,
    infer_sensor_family,
    infer_topic_modality,
    summarize_bag_topics,
    summarize_episode_manifest,
    summarize_topics,
    summarize_visualization_readiness,
)
from hephaes.models import BagMetadata, Topic


def build_bag_metadata(*topics: Topic) -> BagMetadata:
    return BagMetadata(
        compression_format="none",
        duration_seconds=5.0,
        end_time_iso="2026-03-16T10:00:05Z",
        end_timestamp=1_763_117_205_000_000_000,
        file_path="/tmp/test.mcap",
        file_size_bytes=128,
        message_count=sum(topic.message_count for topic in topics),
        path="/tmp/test.mcap",
        ros_version="ROS2",
        start_time_iso="2026-03-16T10:00:00Z",
        start_timestamp=1_763_117_200_000_000_000,
        storage_format="mcap",
        topics=list(topics),
    )


def build_manifest(*, field_names: list[str], rows_written: int) -> EpisodeManifest:
    return EpisodeManifest.model_validate(
        {
            "episode_id": "episode_0001",
            "dataset": {
                "path": "/tmp/output.parquet",
                "format": "parquet",
                "file_size_bytes": 256,
                "rows_written": rows_written,
                "field_names": field_names,
            },
            "source": {
                "path": "/tmp/input.mcap",
                "file_path": "/tmp/input.mcap",
                "ros_version": "ROS2",
                "storage_format": "mcap",
                "file_size_bytes": 1024,
            },
            "temporal": {
                "start_timestamp": 1_000,
                "end_timestamp": 2_000,
                "start_time_iso": "1970-01-01T00:00:00.000001Z",
                "end_time_iso": "1970-01-01T00:00:00.000002Z",
                "duration_seconds": 0.000001,
                "message_count": 2,
            },
            "conversion": {
                "output": {"format": "parquet", "compression": "none"},
                "mapping_requested": {"image": ["/camera/front/image_raw"]},
                "mapping_resolved": {"image": "/camera/front/image_raw"},
            },
        }
    )


def test_infer_topic_modality_matches_existing_heuristics():
    assert infer_topic_modality("sensor_msgs/Image") == "image"
    assert infer_topic_modality("sensor_msgs/PointCloud2") == "points"
    assert infer_topic_modality("sensor_msgs/Imu") == "scalar_series"
    assert infer_topic_modality("nav_msgs/Odometry") == "scalar_series"
    assert infer_topic_modality("custom_msgs/Foo") == "other"


def test_infer_sensor_family_matches_existing_heuristics():
    assert infer_sensor_family("sensor_msgs/Image") == "camera"
    assert infer_sensor_family("sensor_msgs/LaserScan") == "lidar"
    assert infer_sensor_family("sensor_msgs/Imu") == "imu"
    assert infer_sensor_family("sensor_msgs/NavSatFix") == "telemetry"
    assert infer_sensor_family("custom_msgs/Foo") == "other"


def test_visual_modalities_constant_remains_consistent():
    assert VISUAL_MODALITIES == {"image", "points", "scalar_series"}


def test_summarize_topics_supports_empty_topic_sequences():
    summary = summarize_topics([])

    assert summary.modality_counts == {}
    assert summary.sensor_family_counts == {}
    assert summary.visualization.has_visualizable_streams is False
    assert summary.visualization.visualizable_stream_count == 0


def test_summarize_bag_topics_counts_modalities_and_sensor_families_in_topic_order():
    bag_metadata = build_bag_metadata(
        Topic(
            message_count=4,
            message_type="sensor_msgs/Image",
            name="/camera/front/image_raw",
            rate_hz=10.0,
        ),
        Topic(
            message_count=3,
            message_type="sensor_msgs/Imu",
            name="/imu/data",
            rate_hz=20.0,
        ),
        Topic(
            message_count=2,
            message_type="sensor_msgs/LaserScan",
            name="/scan",
            rate_hz=5.0,
        ),
        Topic(
            message_count=1,
            message_type="custom_msgs/Foo",
            name="/custom",
            rate_hz=1.0,
        ),
    )

    summary = summarize_bag_topics(bag_metadata)

    assert summary.modality_counts == {
        "image": 1,
        "scalar_series": 1,
        "points": 1,
        "other": 1,
    }
    assert summary.sensor_family_counts == {
        "camera": 1,
        "imu": 1,
        "lidar": 1,
        "other": 1,
    }
    assert summary.visualization.has_visualizable_streams is True
    assert summary.visualization.visualizable_stream_count == 3


def test_summarize_visualization_readiness_handles_unknown_topics_only():
    readiness = summarize_visualization_readiness(
        [
            Topic(
                message_count=1,
                message_type="custom_msgs/Foo",
                name="/custom",
                rate_hz=1.0,
            )
        ]
    )

    assert readiness.has_visualizable_streams is False
    assert readiness.visualizable_stream_count == 0


def test_summarize_episode_manifest_returns_dataset_summary():
    manifest = build_manifest(field_names=["timestamp_ns", "image"], rows_written=42)

    summary = summarize_episode_manifest(manifest)

    assert summary.dataset_format == "parquet"
    assert summary.rows_written == 42
    assert summary.field_count == 2
    assert summary.field_names == ["timestamp_ns", "image"]
    assert summary.source_ros_version == "ROS2"
    assert summary.source_storage_format == "mcap"


def test_derive_manifest_readiness_flags_handles_missing_manifest():
    flags = derive_manifest_readiness_flags(None, required_fields=["timestamp_ns"])

    assert flags.has_manifest is False
    assert flags.has_rows is False
    assert flags.has_required_fields is False


def test_derive_manifest_readiness_flags_supports_minimal_manifest_fields():
    manifest = build_manifest(field_names=["timestamp_ns"], rows_written=0)

    flags = derive_manifest_readiness_flags(manifest, required_fields=["timestamp_ns"])

    assert flags.has_manifest is True
    assert flags.has_rows is False
    assert flags.has_required_fields is True


def test_derive_manifest_readiness_flags_detects_missing_required_fields():
    manifest = build_manifest(field_names=["timestamp_ns", "image"], rows_written=10)

    flags = derive_manifest_readiness_flags(
        manifest,
        required_fields=["timestamp_ns", "lidar_points"],
    )

    assert flags.has_manifest is True
    assert flags.has_rows is True
    assert flags.has_required_fields is False
