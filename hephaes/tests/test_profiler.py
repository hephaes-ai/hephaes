"""Tests for hephaes.profiler."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from conftest import make_mock_any_reader
from hephaes.models import BagMetadata


def _patch_any_reader(mock_reader):
    return patch("hephaes.reader.AnyReader", return_value=mock_reader)


# ---------------------------------------------------------------------------
# extract_temporal_metadata
# ---------------------------------------------------------------------------

class TestExtractTemporalMetadata:
    def test_uses_reader_start_end_time(self, tmp_bag_file):
        mock_reader = make_mock_any_reader(
            topics={"/t": "std_msgs/String"},
            messages=[("/t", 1_000_000_000, {}), ("/t", 2_000_000_000, {})],
            start_time=1_000_000_000,
            end_time=2_000_000_000,
            message_count=2,
        )
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader
            from hephaes.profiler import extract_temporal_metadata
            reader = ROS1Reader(str(tmp_bag_file))
            tm = extract_temporal_metadata(reader)
            assert tm.start_timestamp == 1_000_000_000
            assert tm.end_timestamp == 2_000_000_000
            assert tm.message_count == 2
            reader.close()

    def test_falls_back_to_message_scan_when_times_none(self, tmp_bag_file):
        mock_reader = make_mock_any_reader(
            topics={"/t": "std_msgs/String"},
            messages=[("/t", 500_000_000, {}), ("/t", 800_000_000, {})],
            start_time=None,
            end_time=None,
            message_count=None,
        )
        # Override start_time/end_time to return None
        mock_reader.start_time = None
        mock_reader.end_time = None
        mock_reader.message_count = 0

        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader
            from hephaes.profiler import extract_temporal_metadata
            reader = ROS1Reader(str(tmp_bag_file))
            tm = extract_temporal_metadata(reader)
            assert tm.start_timestamp == 500_000_000
            assert tm.end_timestamp == 800_000_000
            assert tm.message_count == 2
            reader.close()

    def test_duration_computed_correctly(self, tmp_bag_file):
        mock_reader = make_mock_any_reader(
            start_time=0,
            end_time=5_000_000_000,
            message_count=1,
        )
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader
            from hephaes.profiler import extract_temporal_metadata
            reader = ROS1Reader(str(tmp_bag_file))
            tm = extract_temporal_metadata(reader)
            assert tm.duration_seconds == pytest.approx(5.0)
            reader.close()


# ---------------------------------------------------------------------------
# extract_topics
# ---------------------------------------------------------------------------

class TestExtractTopics:
    def test_returns_topic_list(self, tmp_bag_file):
        mock_reader = make_mock_any_reader(
            topics={"/cmd_vel": "geometry_msgs/Twist"},
            messages=[("/cmd_vel", 1_000_000_000, {}), ("/cmd_vel", 2_000_000_000, {})],
        )
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader
            from hephaes.profiler import extract_topics
            reader = ROS1Reader(str(tmp_bag_file))
            topics = extract_topics(reader)
            assert len(topics) == 1
            assert topics[0].name == "/cmd_vel"
            assert topics[0].message_count == 2
            reader.close()

    def test_rate_computed_for_topic(self, tmp_bag_file):
        # 10 messages over 1 second → 10 Hz
        messages = [("/t", i * 100_000_000, {}) for i in range(10)]
        mock_reader = make_mock_any_reader(
            topics={"/t": "std_msgs/String"},
            messages=messages,
        )
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader
            from hephaes.profiler import extract_topics
            reader = ROS1Reader(str(tmp_bag_file))
            topics = extract_topics(reader)
            assert topics[0].rate_hz > 0
            reader.close()

    def test_multiple_topics(self, tmp_bag_file):
        mock_reader = make_mock_any_reader(
            topics={"/a": "std_msgs/String", "/b": "std_msgs/Int32"},
            messages=[
                ("/a", 1_000_000_000, {}),
                ("/b", 1_500_000_000, {}),
                ("/a", 2_000_000_000, {}),
            ],
        )
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader
            from hephaes.profiler import extract_topics
            reader = ROS1Reader(str(tmp_bag_file))
            topics = extract_topics(reader)
            topic_names = {t.name for t in topics}
            assert "/a" in topic_names
            assert "/b" in topic_names
            reader.close()

    def test_topic_with_single_message_zero_rate(self, tmp_bag_file):
        mock_reader = make_mock_any_reader(
            topics={"/t": "std_msgs/String"},
            messages=[("/t", 1_000_000_000, {})],
        )
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader
            from hephaes.profiler import extract_topics
            reader = ROS1Reader(str(tmp_bag_file))
            topics = extract_topics(reader)
            assert topics[0].rate_hz == 0.0
            reader.close()


# ---------------------------------------------------------------------------
# Profiler class
# ---------------------------------------------------------------------------

class TestProfiler:
    def test_init_not_list_raises(self):
        from hephaes.profiler import Profiler
        with pytest.raises(TypeError, match="must be a list"):
            Profiler("not_a_list")

    def test_init_empty_list_raises(self):
        from hephaes.profiler import Profiler
        with pytest.raises(ValueError, match="non-empty"):
            Profiler([])

    def test_init_invalid_extension_raises(self, tmp_path):
        from hephaes.profiler import Profiler
        p = tmp_path / "file.txt"
        p.write_bytes(b"")
        with pytest.raises(ValueError):
            Profiler([str(p)])

    def test_init_max_workers_zero_raises(self, tmp_bag_file):
        from hephaes.profiler import Profiler
        with pytest.raises(ValueError, match="max_workers"):
            Profiler([str(tmp_bag_file)], max_workers=0)

    def test_init_valid(self, tmp_bag_file):
        from hephaes.profiler import Profiler
        p = Profiler([str(tmp_bag_file)])
        assert len(p.bag_paths) == 1

    def test_profile_returns_list_of_models(self, tmp_bag_file):
        mock_reader = make_mock_any_reader(
            topics={"/cmd_vel": "geometry_msgs/Twist"},
            messages=[("/cmd_vel", 1_000_000_000, {}), ("/cmd_vel", 2_000_000_000, {})],
            start_time=1_000_000_000,
            end_time=2_000_000_000,
            message_count=2,
        )
        with _patch_any_reader(mock_reader):
            from hephaes.profiler import Profiler
            profiler = Profiler([str(tmp_bag_file)], max_workers=1)
            results = profiler.profile()
            assert isinstance(results, list)
            assert len(results) == 1
            result = results[0]
            assert isinstance(result, BagMetadata)
            assert result.ros_version == "ROS1"
            assert result.topics

    def test_profile_multiple_bags(self, tmp_path):
        bag1 = tmp_path / "bag1.bag"
        bag2 = tmp_path / "bag2.bag"
        bag1.write_bytes(b"")
        bag2.write_bytes(b"")

        mock_reader = make_mock_any_reader(
            topics={"/t": "std_msgs/String"},
            messages=[("/t", 1_000_000_000, {}), ("/t", 2_000_000_000, {})],
            start_time=1_000_000_000,
            end_time=2_000_000_000,
            message_count=2,
        )
        with _patch_any_reader(mock_reader):
            from hephaes.profiler import Profiler
            profiler = Profiler([str(bag1), str(bag2)], max_workers=1)
            results = profiler.profile()
            assert len(results) == 2
