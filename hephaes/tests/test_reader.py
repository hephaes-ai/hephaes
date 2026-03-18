"""Tests for hephaes.reader (RosReader, ROS1Reader, ROS2Reader)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from conftest import make_mock_any_reader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_any_reader(mock_reader):
    """Context manager that patches rosbags AnyReader."""
    return patch("hephaes.reader.AnyReader", return_value=mock_reader)


# ---------------------------------------------------------------------------
# RosReader.open  (factory)
# ---------------------------------------------------------------------------

class TestRosReaderOpen:
    def test_open_ros1_from_extension(self, tmp_bag_file):
        mock_reader = make_mock_any_reader()
        with _patch_any_reader(mock_reader):
            from hephaes.reader import RosReader, ROS1Reader
            reader = RosReader.open(str(tmp_bag_file))
            assert isinstance(reader, ROS1Reader)
            reader.close()

    def test_open_ros2_from_extension(self, tmp_mcap_file):
        mock_reader = make_mock_any_reader()
        with _patch_any_reader(mock_reader):
            from hephaes.reader import RosReader, ROS2Reader
            reader = RosReader.open(str(tmp_mcap_file))
            assert isinstance(reader, ROS2Reader)
            reader.close()

    def test_open_with_explicit_ros_version(self, tmp_bag_file):
        mock_reader = make_mock_any_reader()
        with _patch_any_reader(mock_reader):
            from hephaes.reader import RosReader, ROS1Reader
            reader = RosReader.open(str(tmp_bag_file), ros_version="ROS1")
            assert isinstance(reader, ROS1Reader)
            reader.close()

    def test_open_unsupported_version_raises(self, tmp_bag_file):
        mock_reader = make_mock_any_reader()
        with _patch_any_reader(mock_reader):
            from hephaes.reader import RosReader
            with pytest.raises(ValueError, match="Unsupported ROS version"):
                RosReader.open(str(tmp_bag_file), ros_version="ROS3")

    def test_open_with_custom_registry(self, tmp_bag_file):
        mock_reader = make_mock_any_reader()
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader, ReaderRegistry, RosReader

            registry = ReaderRegistry()
            registry.register("ROS1", ROS1Reader)
            reader = RosReader.open(str(tmp_bag_file), ros_version="ROS1", registry=registry)
            assert isinstance(reader, ROS1Reader)
            reader.close()


# ---------------------------------------------------------------------------
# ROS1Reader
# ---------------------------------------------------------------------------

class TestROS1Reader:
    def test_init_file_not_found(self, tmp_path):
        from hephaes.reader import ROS1Reader
        with pytest.raises(FileNotFoundError):
            ROS1Reader(str(tmp_path / "missing.bag"))

    def test_init_not_a_bag_extension_raises(self, tmp_path):
        p = tmp_path / "test.mcap"
        p.write_bytes(b"")
        mock_reader = make_mock_any_reader()
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader
            with pytest.raises(ValueError, match=".bag"):
                ROS1Reader(str(p))

    def test_init_directory_raises(self, tmp_path):
        from hephaes.reader import ROS1Reader
        with pytest.raises(ValueError, match=".bag file path"):
            ROS1Reader(str(tmp_path))

    def test_topics_populated(self, tmp_bag_file):
        mock_reader = make_mock_any_reader(topics={"/cmd_vel": "geometry_msgs/Twist"})
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader
            reader = ROS1Reader(str(tmp_bag_file))
            assert "/cmd_vel" in reader.topics
            reader.close()

    def test_metadata(self, tmp_bag_file):
        mock_reader = make_mock_any_reader()
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader
            reader = ROS1Reader(str(tmp_bag_file))
            meta = reader.metadata
            assert meta.ros_version == "ROS1"
            assert meta.storage_format == "bag"
            reader.close()

    def test_extract_internal_statistics(self, tmp_bag_file):
        mock_reader = make_mock_any_reader()
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader
            reader = ROS1Reader(str(tmp_bag_file))
            stats = reader.extract_internal_statistics()
            assert stats.compression_format in {"zstd", "lz4", "bz2", "none", "unknown"}
            reader.close()

    def test_context_manager(self, tmp_bag_file):
        mock_reader = make_mock_any_reader()
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader
            with ROS1Reader(str(tmp_bag_file)) as reader:
                assert reader.ros_version == "ROS1"

    def test_read_messages_yields_messages(self, tmp_bag_file):
        msgs = [("/cmd_vel", 1_000_000_000, {"v": 1})]
        mock_reader = make_mock_any_reader(
            topics={"/cmd_vel": "geometry_msgs/Twist"},
            messages=msgs,
        )
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader
            reader = ROS1Reader(str(tmp_bag_file))
            result = list(reader.read_messages())
            assert len(result) == 1
            assert result[0].topic == "/cmd_vel"
            assert result[0].timestamp == 1_000_000_000
            reader.close()

    def test_read_messages_topic_filter(self, tmp_bag_file):
        msgs = [
            ("/cmd_vel", 1_000_000_000, {}),
            ("/odom", 1_500_000_000, {}),
        ]
        mock_reader = make_mock_any_reader(
            topics={"/cmd_vel": "geometry_msgs/Twist", "/odom": "nav_msgs/Odometry"},
            messages=msgs,
        )
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader
            reader = ROS1Reader(str(tmp_bag_file))
            result = list(reader.read_messages(topics=["/cmd_vel"]))
            assert all(m.topic == "/cmd_vel" for m in result)
            reader.close()

    def test_read_messages_prints_skip_statement_on_deserialize_failure(self, tmp_bag_file, capsys):
        msgs = [
            ("/cmd_vel", 1_000_000_000, {}),
            ("/cmd_vel", 2_000_000_000, {}),
        ]
        mock_reader = make_mock_any_reader(
            topics={"/cmd_vel": "geometry_msgs/Twist"},
            messages=msgs,
        )

        deserialize_calls = {"count": 0}

        def _deserialize(rawdata, msgtype):
            deserialize_calls["count"] += 1
            if deserialize_calls["count"] == 1:
                raise ValueError("bad payload")
            return {"value": 2}

        mock_reader.deserialize = _deserialize

        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader

            reader = ROS1Reader(str(tmp_bag_file))
            result = list(reader.read_messages())
            captured = capsys.readouterr()

            assert len(result) == 1
            assert "Skipping message due to deserialization failure" in captured.err
            assert "bad payload" in captured.err
            reader.close()

    def test_start_time_end_time(self, tmp_bag_file):
        mock_reader = make_mock_any_reader(start_time=100, end_time=200)
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader
            reader = ROS1Reader(str(tmp_bag_file))
            assert reader.start_time == 100
            assert reader.end_time == 200
            reader.close()

    def test_message_count(self, tmp_bag_file):
        mock_reader = make_mock_any_reader(message_count=42)
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader
            reader = ROS1Reader(str(tmp_bag_file))
            assert reader.message_count == 42
            reader.close()

    def test_repr(self, tmp_bag_file):
        mock_reader = make_mock_any_reader()
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS1Reader
            reader = ROS1Reader(str(tmp_bag_file))
            r = repr(reader)
            assert "ROS1Reader" in r
            reader.close()


# ---------------------------------------------------------------------------
# ROS2Reader
# ---------------------------------------------------------------------------

class TestROS2Reader:
    def test_init_file_not_found(self, tmp_path):
        from hephaes.reader import ROS2Reader
        with pytest.raises(FileNotFoundError):
            ROS2Reader(str(tmp_path / "missing.mcap"))

    def test_init_wrong_extension_raises(self, tmp_path):
        p = tmp_path / "test.bag"
        p.write_bytes(b"")
        mock_reader = make_mock_any_reader()
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS2Reader
            with pytest.raises(ValueError, match=".mcap"):
                ROS2Reader(str(p))

    def test_init_directory_raises(self, tmp_path):
        from hephaes.reader import ROS2Reader
        with pytest.raises(ValueError):
            ROS2Reader(str(tmp_path))

    def test_topics_populated(self, tmp_mcap_file):
        mock_reader = make_mock_any_reader(topics={"/scan": "sensor_msgs/LaserScan"})
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS2Reader
            reader = ROS2Reader(str(tmp_mcap_file))
            assert "/scan" in reader.topics
            reader.close()

    def test_metadata_no_yaml(self, tmp_mcap_file):
        mock_reader = make_mock_any_reader()
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS2Reader
            reader = ROS2Reader(str(tmp_mcap_file))
            meta = reader.metadata
            assert meta.ros_version == "ROS2"
            assert meta.storage_format == "mcap"
            assert meta.source_metadata is None
            reader.close()

    def test_metadata_with_yaml(self, tmp_path):
        mcap = tmp_path / "test.mcap"
        mcap.write_bytes(b"")
        yaml_file = tmp_path / "metadata.yaml"
        yaml_file.write_text("rosbag2_bagfile_information:\n  version: 5\n")
        mock_reader = make_mock_any_reader()
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS2Reader
            reader = ROS2Reader(str(mcap))
            meta = reader.metadata
            assert meta.source_metadata is not None
            reader.close()

    def test_metadata_cached(self, tmp_path):
        mcap = tmp_path / "test.mcap"
        mcap.write_bytes(b"")
        yaml_file = tmp_path / "metadata.yaml"
        yaml_file.write_text("rosbag2_bagfile_information:\n  version: 5\n")
        mock_reader = make_mock_any_reader()
        with patch("hephaes.reader.yaml.safe_load", return_value={"ok": True}) as safe_load:
            with _patch_any_reader(mock_reader):
                from hephaes.reader import ROS2Reader

                reader = ROS2Reader(str(mcap))
                first = reader.metadata
                second = reader.metadata
                assert first is second
                assert safe_load.call_count == 1
                reader.close()

    def test_close_clears_metadata_cache(self, tmp_path):
        mcap = tmp_path / "test.mcap"
        mcap.write_bytes(b"")
        yaml_file = tmp_path / "metadata.yaml"
        yaml_file.write_text("rosbag2_bagfile_information:\n  version: 5\n")
        mock_reader = make_mock_any_reader()
        with patch("hephaes.reader.yaml.safe_load", return_value={"ok": True}) as safe_load:
            with _patch_any_reader(mock_reader):
                from hephaes.reader import ROS2Reader

                reader = ROS2Reader(str(mcap))
                first = reader.metadata
                reader.close()
                second = reader.metadata

                assert first is not second
                assert safe_load.call_count == 2
                reader.close()

    def test_context_manager(self, tmp_mcap_file):
        mock_reader = make_mock_any_reader()
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS2Reader
            with ROS2Reader(str(tmp_mcap_file)) as reader:
                assert reader.ros_version == "ROS2"

    def test_extract_internal_statistics(self, tmp_mcap_file):
        mock_reader = make_mock_any_reader()
        with _patch_any_reader(mock_reader):
            from hephaes.reader import ROS2Reader
            reader = ROS2Reader(str(tmp_mcap_file))
            stats = reader.extract_internal_statistics()
            assert stats.compression_format in {"zstd", "lz4", "bz2", "none", "unknown"}
            reader.close()
