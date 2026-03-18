"""Tests for hephaes.models."""
import pytest
from pydantic import ValidationError

from hephaes.models import (
    BagMetadata,
    EpisodeRef,
    GroupingConfig,
    InternalStats,
    MappingTemplate,
    Message,
    ParquetOutputConfig,
    ReaderMetadata,
    TFRecordOutputConfig,
    TemporalMetadata,
    Topic,
)


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

class TestMessage:
    def test_valid(self):
        msg = Message(timestamp=1000, topic="/cmd_vel", data={"x": 1})
        assert msg.timestamp == 1000
        assert msg.topic == "/cmd_vel"

    def test_negative_timestamp_rejected(self):
        with pytest.raises(ValidationError):
            Message(timestamp=-1, topic="/cmd_vel", data=None)

    def test_empty_topic_rejected(self):
        with pytest.raises(ValidationError):
            Message(timestamp=0, topic="", data=None)

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            Message(timestamp=0, topic="/t", data=None, extra_field="bad")

    def test_data_can_be_none(self):
        msg = Message(timestamp=0, topic="/t", data=None)
        assert msg.data is None


# ---------------------------------------------------------------------------
# InternalStats
# ---------------------------------------------------------------------------

class TestInternalStats:
    @pytest.mark.parametrize("fmt", ["zstd", "lz4", "bz2", "none", "unknown"])
    def test_valid_formats(self, fmt):
        stats = InternalStats(compression_format=fmt)
        assert stats.compression_format == fmt

    def test_invalid_format_rejected(self):
        with pytest.raises(ValidationError):
            InternalStats(compression_format="gzip")

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            InternalStats(compression_format="none", extra="bad")


# ---------------------------------------------------------------------------
# GroupingConfig
# ---------------------------------------------------------------------------

class TestGroupingConfig:
    def test_default_method(self):
        cfg = GroupingConfig()
        assert cfg.method == "bag"

    def test_explicit_bag(self):
        cfg = GroupingConfig(method="bag")
        assert cfg.method == "bag"


# ---------------------------------------------------------------------------
# Output Configs
# ---------------------------------------------------------------------------

class TestOutputConfigs:
    def test_parquet_output_defaults(self):
        cfg = ParquetOutputConfig()
        assert cfg.format == "parquet"
        assert cfg.compression == "none"

    def test_tfrecord_output_defaults(self):
        cfg = TFRecordOutputConfig()
        assert cfg.format == "tfrecord"
        assert cfg.compression == "none"
        assert cfg.payload_encoding == "typed_features"
        assert cfg.null_encoding == "presence_flag"

    def test_invalid_parquet_compression_rejected(self):
        with pytest.raises(ValidationError):
            ParquetOutputConfig(compression="bad")

    def test_invalid_tfrecord_compression_rejected(self):
        with pytest.raises(ValidationError):
            TFRecordOutputConfig(compression="snappy")


# ---------------------------------------------------------------------------
# EpisodeRef
# ---------------------------------------------------------------------------

class TestEpisodeRef:
    def test_valid(self):
        ref = EpisodeRef(episode_id="ep1", bag_path="/data/test.bag")
        assert ref.episode_id == "ep1"
        assert ref.bag_path == "/data/test.bag"

    def test_empty_episode_id_rejected(self):
        with pytest.raises(ValidationError):
            EpisodeRef(episode_id="", bag_path="/data/test.bag")

    def test_empty_bag_path_rejected(self):
        with pytest.raises(ValidationError):
            EpisodeRef(episode_id="ep1", bag_path="")


# ---------------------------------------------------------------------------
# MappingTemplate
# ---------------------------------------------------------------------------

class TestMappingTemplate:
    def test_valid(self):
        mt = MappingTemplate.model_validate({"cmd_vel": ["/cmd_vel"]})
        assert mt.root == {"cmd_vel": ["/cmd_vel"]}

    def test_multiple_sources(self):
        mt = MappingTemplate.model_validate({"vel": ["/cmd_vel", "/vel"]})
        assert mt.root["vel"] == ["/cmd_vel", "/vel"]

    def test_empty_target_field_rejected(self):
        with pytest.raises(ValidationError):
            MappingTemplate.model_validate({"": ["/cmd_vel"]})

    def test_empty_source_topic_rejected(self):
        with pytest.raises(ValidationError):
            MappingTemplate.model_validate({"cmd_vel": [""]})

    def test_non_list_value_rejected(self):
        with pytest.raises(ValidationError):
            MappingTemplate.model_validate({"cmd_vel": "/cmd_vel"})

    def test_empty_mapping_allowed(self):
        mt = MappingTemplate.model_validate({})
        assert mt.root == {}


# ---------------------------------------------------------------------------
# ReaderMetadata
# ---------------------------------------------------------------------------

class TestReaderMetadata:
    def test_valid_ros1(self):
        meta = ReaderMetadata(
            path="/data/test.bag",
            file_path="/data/test.bag",
            ros_version="ROS1",
            storage_format="bag",
            file_size_bytes=1024,
        )
        assert meta.ros_version == "ROS1"
        assert meta.storage_format == "bag"

    def test_valid_ros2(self):
        meta = ReaderMetadata(
            path="/data/test.mcap",
            file_path="/data/test.mcap",
            ros_version="ROS2",
            storage_format="mcap",
            file_size_bytes=0,
        )
        assert meta.ros_version == "ROS2"

    def test_negative_file_size_rejected(self):
        with pytest.raises(ValidationError):
            ReaderMetadata(
                path="/data/test.bag",
                file_path="/data/test.bag",
                ros_version="ROS1",
                storage_format="bag",
                file_size_bytes=-1,
            )

    def test_empty_path_rejected(self):
        with pytest.raises(ValidationError):
            ReaderMetadata(
                path="",
                file_path="/data/test.bag",
                ros_version="ROS1",
                storage_format="bag",
                file_size_bytes=0,
            )

    def test_source_metadata_optional(self):
        meta = ReaderMetadata(
            path="/data/test.bag",
            file_path="/data/test.bag",
            ros_version="ROS1",
            storage_format="bag",
            file_size_bytes=0,
        )
        assert meta.source_metadata is None

    def test_source_metadata_set(self):
        meta = ReaderMetadata(
            path="/data/test.bag",
            file_path="/data/test.bag",
            ros_version="ROS1",
            storage_format="bag",
            file_size_bytes=0,
            source_metadata={"key": "val"},
        )
        assert meta.source_metadata == {"key": "val"}


# ---------------------------------------------------------------------------
# TemporalMetadata
# ---------------------------------------------------------------------------

class TestTemporalMetadata:
    def test_valid_with_timestamps(self):
        tm = TemporalMetadata(
            start_timestamp=1_000_000_000,
            end_timestamp=2_000_000_000,
            start_time_iso="1970-01-01T00:00:01Z",
            end_time_iso="1970-01-01T00:00:02Z",
            duration_seconds=1.0,
            message_count=10,
        )
        assert tm.duration_seconds == 1.0

    def test_valid_no_timestamps(self):
        tm = TemporalMetadata(
            duration_seconds=0.0,
            message_count=0,
        )
        assert tm.start_timestamp is None
        assert tm.end_timestamp is None

    def test_end_before_start_rejected(self):
        with pytest.raises(ValidationError):
            TemporalMetadata(
                start_timestamp=2_000_000_000,
                end_timestamp=1_000_000_000,
                duration_seconds=0.0,
                message_count=0,
            )

    def test_only_start_set_rejected(self):
        with pytest.raises(ValidationError):
            TemporalMetadata(
                start_timestamp=1_000_000_000,
                duration_seconds=0.0,
                message_count=0,
            )

    def test_negative_duration_rejected(self):
        with pytest.raises(ValidationError):
            TemporalMetadata(duration_seconds=-1.0, message_count=0)

    def test_negative_message_count_rejected(self):
        with pytest.raises(ValidationError):
            TemporalMetadata(duration_seconds=0.0, message_count=-1)

    def test_equal_start_end_allowed(self):
        tm = TemporalMetadata(
            start_timestamp=1_000_000_000,
            end_timestamp=1_000_000_000,
            duration_seconds=0.0,
            message_count=1,
        )
        assert tm.start_timestamp == tm.end_timestamp


# ---------------------------------------------------------------------------
# Topic
# ---------------------------------------------------------------------------

class TestTopic:
    def test_valid(self):
        t = Topic(name="/cmd_vel", message_type="geometry_msgs/Twist", message_count=100, rate_hz=10.0)
        assert t.name == "/cmd_vel"
        assert t.rate_hz == 10.0

    def test_zero_rate_allowed(self):
        t = Topic(name="/t", message_type="std_msgs/String", message_count=0, rate_hz=0.0)
        assert t.rate_hz == 0.0

    def test_negative_rate_rejected(self):
        with pytest.raises(ValidationError):
            Topic(name="/t", message_type="std_msgs/String", message_count=0, rate_hz=-1.0)

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            Topic(name="", message_type="std_msgs/String", message_count=0, rate_hz=0.0)


# ---------------------------------------------------------------------------
# BagMetadata
# ---------------------------------------------------------------------------

class TestBagMetadata:
    def _valid_kwargs(self):
        return dict(
            path="/data/test.bag",
            file_path="/data/test.bag",
            ros_version="ROS1",
            storage_format="bag",
            file_size_bytes=1024,
            start_timestamp=1_000_000_000,
            end_timestamp=2_000_000_000,
            start_time_iso="1970-01-01T00:00:01Z",
            end_time_iso="1970-01-01T00:00:02Z",
            duration_seconds=1.0,
            message_count=10,
            topics=[Topic(name="/t", message_type="std_msgs/String", message_count=10, rate_hz=10.0)],
            compression_format="none",
        )

    def test_valid(self):
        bm = BagMetadata(**self._valid_kwargs())
        assert bm.ros_version == "ROS1"
        assert len(bm.topics) == 1

    def test_empty_topics_list_allowed(self):
        kwargs = self._valid_kwargs()
        kwargs["topics"] = []
        bm = BagMetadata(**kwargs)
        assert bm.topics == []
