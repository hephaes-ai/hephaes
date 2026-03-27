"""Tests for hephaes.converter."""
from __future__ import annotations

import base64
import importlib.util
import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from hephaes._converter_helpers import _normalize_payload
from hephaes.converter import _interpolate_json_leaves, _json_default, _resolve_mapping_for_bag
from hephaes.models import (
    ConversionSpec,
    MappingTemplate,
    OutputSpec,
    ResampleConfig,
    SchemaSpec,
    TFRecordOutputConfig,
)

_HAS_PYARROW = importlib.util.find_spec("pyarrow") is not None


def _patch_any_reader(mock_reader: MagicMock):
    return patch("hephaes.reader.AnyReader", return_value=mock_reader)


def _make_connection(topic: str, msgtype: str) -> MagicMock:
    conn = MagicMock()
    conn.topic = topic
    conn.msgtype = msgtype
    return conn


def make_mock_any_reader_with_payloads(
    *,
    topics: dict[str, str],
    messages: list[tuple[str, int, object]],
) -> MagicMock:
    """Create an AnyReader mock with stable raw payloads and typed deserialization."""
    connections = [_make_connection(topic, msgtype) for topic, msgtype in topics.items()]
    conn_by_topic = {conn.topic: conn for conn in connections}

    records: list[tuple[str, int, bytes]] = []
    payload_by_raw: dict[bytes, object] = {}
    for idx, (topic, timestamp, payload) in enumerate(messages):
        raw = f"raw-{idx}".encode("ascii")
        records.append((topic, timestamp, raw))
        payload_by_raw[raw] = payload

    mock_reader = MagicMock()
    mock_reader.start_time = records[0][1] if records else None
    mock_reader.end_time = records[-1][1] if records else None
    mock_reader.message_count = len(records)
    mock_reader.topics = {conn.topic: conn for conn in connections}
    mock_reader.connections = connections

    def _messages(connections=None, start=None, stop=None):
        conns_to_use = connections or mock_reader.connections
        topic_set = {conn.topic for conn in conns_to_use}
        for topic, timestamp, raw in records:
            if topic in topic_set:
                if start is not None and timestamp < start:
                    continue
                if stop is not None and timestamp >= stop:
                    continue
                yield conn_by_topic[topic], timestamp, raw

    def _deserialize(rawdata, msgtype):
        return payload_by_raw[rawdata]

    mock_reader.messages = MagicMock(side_effect=_messages)
    mock_reader.deserialize = _deserialize
    return mock_reader


class TestJsonDefault:
    def test_bytes_encoded_as_base64(self):
        result = _json_default(b"\x00\x01\x02")
        assert result["__bytes__"] is True
        assert result["encoding"] == "base64"
        assert "value" in result

    def test_set_converted_to_list(self):
        result = _json_default({1, 2, 3})
        assert isinstance(result, list)
        assert sorted(result) == [1, 2, 3]


class TestNormalizePayload:
    def test_numpy_scalar_and_array_round_trip_to_python_values(self):
        assert _normalize_payload(np.int64(7)) == 7
        assert _normalize_payload(np.float32(0.25)) == pytest.approx(0.25)
        assert _normalize_payload(np.array([1, 2, 3])) == [1, 2, 3]


class TestResolveMappingForBag:
    def test_matching_topic(self):
        mapping = MappingTemplate.model_validate({"cmd_vel": ["/cmd_vel"]})
        plan = _resolve_mapping_for_bag(
            mapping=mapping,
            available_topics={"/cmd_vel": "geometry_msgs/Twist"},
        )
        assert plan.topics_to_read == ["/cmd_vel"]
        assert plan.topic_to_field["/cmd_vel"] == "cmd_vel"

    def test_fallback_source_topic(self):
        mapping = MappingTemplate.model_validate({"vel": ["/missing", "/cmd_vel"]})
        plan = _resolve_mapping_for_bag(
            mapping=mapping,
            available_topics={"/cmd_vel": "geometry_msgs/Twist"},
        )
        assert plan.topics_to_read == ["/cmd_vel"]
        assert plan.topic_to_field["/cmd_vel"] == "vel"

    def test_unavailable_topics_skipped(self):
        mapping = MappingTemplate.model_validate({"field": ["/nonexistent"]})
        plan = _resolve_mapping_for_bag(
            mapping=mapping,
            available_topics={"/cmd_vel": "geometry_msgs/Twist"},
        )
        assert plan.topics_to_read == []
        assert plan.topic_to_field == {}


class TestInterpolateJsonLeaves:
    def test_scalar_numbers(self):
        assert _interpolate_json_leaves(0.0, 4.0, 0.5) == pytest.approx(2.0)

    def test_dict_numeric_leaves(self):
        result = _interpolate_json_leaves({"x": 0.0, "y": 10.0}, {"x": 2.0, "y": 20.0}, 0.5)
        assert result["x"] == pytest.approx(1.0)
        assert result["y"] == pytest.approx(15.0)

    def test_non_numeric_forward_fills(self):
        result = _interpolate_json_leaves("hello", "world", 0.5)
        assert result == "hello"


class TestConverter:
    def _make_mapping(self):
        return MappingTemplate.model_validate({"cmd_vel": ["/cmd_vel"]})

    def test_init_not_list_raises(self, tmp_path):
        from hephaes.converter import Converter

        with pytest.raises(TypeError, match="must be a list"):
            Converter("not_a_list", self._make_mapping(), tmp_path)

    def test_init_empty_list_raises(self, tmp_path):
        from hephaes.converter import Converter

        with pytest.raises(ValueError, match="non-empty"):
            Converter([], self._make_mapping(), tmp_path)

    def test_init_invalid_bag_extension_raises(self, tmp_path):
        from hephaes.converter import Converter

        p = tmp_path / "file.txt"
        p.write_bytes(b"")
        with pytest.raises(ValueError):
            Converter([str(p)], self._make_mapping(), tmp_path)

    def test_init_invalid_max_workers_raises(self, tmp_bag_file, tmp_path):
        from hephaes.converter import Converter

        with pytest.raises(ValueError, match="max_workers"):
            Converter([str(tmp_bag_file)], self._make_mapping(), tmp_path, max_workers=0)

    def test_init_invalid_chunk_rows_raises(self, tmp_bag_file, tmp_path):
        from hephaes.converter import Converter

        with pytest.raises(ValueError, match="chunk_rows"):
            Converter([str(tmp_bag_file)], self._make_mapping(), tmp_path, chunk_rows=0)

    def test_init_invalid_resample_type_raises(self, tmp_bag_file, tmp_path):
        from hephaes.converter import Converter

        with pytest.raises(TypeError, match="ResampleConfig"):
            Converter([str(tmp_bag_file)], self._make_mapping(), tmp_path, resample={"freq_hz": 10.0, "method": "downsample"})  # type: ignore[arg-type]

    def test_init_invalid_output_type_raises(self, tmp_bag_file, tmp_path):
        from hephaes.converter import Converter

        with pytest.raises(TypeError, match="output"):
            Converter([str(tmp_bag_file)], self._make_mapping(), tmp_path, output={"format": "tfrecord"})  # type: ignore[arg-type]

    def test_init_invalid_output_string_raises(self, tmp_bag_file, tmp_path):
        from hephaes.converter import Converter

        with pytest.raises(ValueError, match="output"):
            Converter([str(tmp_bag_file)], self._make_mapping(), tmp_path, output="csv")

    @pytest.mark.skipif(not _HAS_PYARROW, reason="pyarrow not installed")
    def test_convert_returns_parquet_paths(self, tmp_bag_file, tmp_path):
        mock_reader = make_mock_any_reader_with_payloads(
            topics={"/cmd_vel": "geometry_msgs/Twist"},
            messages=[("/cmd_vel", 1_000_000_000, {"v": 1}), ("/cmd_vel", 2_000_000_000, {"v": 2})],
        )
        with _patch_any_reader(mock_reader):
            from hephaes.converter import Converter

            converter = Converter([str(tmp_bag_file)], self._make_mapping(), tmp_path, max_workers=1)
            results = converter.convert()
            assert len(results) == 1
            assert results[0].suffix == ".parquet"
            assert results[0].exists()

    @pytest.mark.skipif(not _HAS_PYARROW, reason="pyarrow not installed")
    def test_convert_no_resample_uses_union_timestamps_with_nulls(self, tmp_bag_file, tmp_path):
        from hephaes.parquet import stream_wide_parquet_rows

        mapping = MappingTemplate.model_validate({"cmd_vel": ["/cmd_vel"], "odom": ["/odom"]})
        mock_reader = make_mock_any_reader_with_payloads(
            topics={"/cmd_vel": "geometry_msgs/Twist", "/odom": "nav_msgs/Odometry"},
            messages=[
                ("/cmd_vel", 1_000_000_000, {"v": 1}),
                ("/odom", 2_000_000_000, {"pose": {}}),
            ],
        )

        with _patch_any_reader(mock_reader):
            from hephaes.converter import Converter

            converter = Converter([str(tmp_bag_file)], mapping, tmp_path, max_workers=1)
            results = converter.convert()

        rows = list(stream_wide_parquet_rows(results[0]))
        assert [row["timestamp_ns"] for row in rows] == [1_000_000_000, 2_000_000_000]
        assert rows[0]["cmd_vel"] is not None
        assert rows[0]["odom"] is None
        assert rows[1]["cmd_vel"] is None
        assert rows[1]["odom"] is not None

    def test_convert_returns_tfrecord_paths(self, tmp_bag_file, tmp_path):
        from hephaes.converter import Converter
        from hephaes.tfrecord import stream_tfrecord_rows

        mock_reader = make_mock_any_reader_with_payloads(
            topics={"/cmd_vel": "geometry_msgs/Twist"},
            messages=[("/cmd_vel", 1_000_000_000, {"v": 1}), ("/cmd_vel", 2_000_000_000, {"v": 2})],
        )
        with _patch_any_reader(mock_reader):
            converter = Converter(
                [str(tmp_bag_file)],
                self._make_mapping(),
                tmp_path,
                max_workers=1,
                output="tfrecord",
            )
            results = converter.convert()

        assert len(results) == 1
        assert results[0].suffix == ".tfrecord"
        assert results[0].exists()
        rows = list(stream_tfrecord_rows(results[0]))
        assert [row["timestamp_ns"] for row in rows] == [1_000_000_000, 2_000_000_000]
        assert rows[0]["cmd_vel__present"] == 1
        assert rows[0]["cmd_vel__v"] == 1

    def test_convert_tfrecord_preserves_numpy_payloads(self, tmp_bag_file, tmp_path):
        from hephaes.converter import Converter
        from hephaes.tfrecord import stream_tfrecord_rows

        mock_reader = make_mock_any_reader_with_payloads(
            topics={"/cmd_vel": "geometry_msgs/Twist"},
            messages=[
                (
                    "/cmd_vel",
                    1_000_000_000,
                    {
                        "covariance": np.array([1, 2, 3]),
                        "count": np.int64(7),
                        "gain": np.float32(0.25),
                    },
                )
            ],
        )

        with _patch_any_reader(mock_reader):
            converter = Converter(
                [str(tmp_bag_file)],
                self._make_mapping(),
                tmp_path,
                max_workers=1,
                output="tfrecord",
            )
            results = converter.convert()

        rows = list(stream_tfrecord_rows(results[0]))
        assert len(rows) == 1
        row = rows[0]
        assert row["timestamp_ns"] == 1_000_000_000
        assert row["cmd_vel__present"] == 1
        assert row["cmd_vel__covariance"] == [1, 2, 3]
        assert row["cmd_vel__count"] == 7
        assert row["cmd_vel__gain"] == pytest.approx(0.25)

    def test_convert_writes_manifest_with_defaults_and_robot_context(self, tmp_bag_file, tmp_path):
        from hephaes.converter import Converter

        mock_reader = make_mock_any_reader_with_payloads(
            topics={"/cmd_vel": "geometry_msgs/Twist"},
            messages=[
                ("/cmd_vel", 1_000_000_000, {"v": 1}),
                ("/cmd_vel", 2_000_000_000, {"v": 2}),
            ],
        )
        with _patch_any_reader(mock_reader):
            converter = Converter(
                [str(tmp_bag_file)],
                self._make_mapping(),
                tmp_path,
                max_workers=1,
                output="tfrecord",
                robot_context={"robot_id": "r2d2", "platform": "spot"},
            )
            results = converter.convert()

        manifest_path = results[0].with_suffix(".manifest.json")
        manifest = json.loads(manifest_path.read_text())

        assert manifest_path.exists()
        assert manifest["manifest_version"] == 1
        assert manifest["episode_id"] == "episode_0001"
        assert manifest["dataset"]["path"] == str(results[0])
        assert manifest["dataset"]["format"] == "tfrecord"
        assert manifest["dataset"]["rows_written"] == 2
        assert manifest["dataset"]["field_names"] == ["cmd_vel"]
        assert manifest["source"]["path"] == str(tmp_bag_file)
        assert manifest["source"]["source_metadata"] is None
        assert manifest["conversion"]["mapping_requested"] == {"cmd_vel": ["/cmd_vel"]}
        assert manifest["conversion"]["mapping_resolved"] == {"cmd_vel": "/cmd_vel"}
        assert manifest["conversion"]["schema"] == {
            "name": "legacy_mapping",
            "version": 1,
        }
        assert manifest["robot_context"] == {"robot_id": "r2d2", "platform": "spot"}
        assert manifest["labels"] == {
            "auto_tags": None,
            "vlm_description": None,
            "objects_detected": None,
        }
        assert manifest["privacy"] == {
            "is_anonymized": False,
            "anonymization_method": None,
        }

    def test_convert_manifest_includes_ros2_source_metadata(self, tmp_mcap_file, tmp_path):
        from hephaes.converter import Converter

        metadata_yaml = tmp_path / "metadata.yaml"
        metadata_yaml.write_text("rosbag2_bagfile_information:\n  version: 5\n")
        mock_reader = make_mock_any_reader_with_payloads(
            topics={"/cmd_vel": "geometry_msgs/Twist"},
            messages=[("/cmd_vel", 1_000_000_000, {"v": 1})],
        )

        with _patch_any_reader(mock_reader):
            converter = Converter(
                [str(tmp_mcap_file)],
                self._make_mapping(),
                tmp_path,
                max_workers=1,
                output="tfrecord",
            )
            results = converter.convert()

        manifest = json.loads(results[0].with_suffix(".manifest.json").read_text())
        assert manifest["source"]["ros_version"] == "ROS2"
        assert manifest["source"]["storage_format"] == "mcap"
        assert manifest["source"]["source_metadata"] == {
            "rosbag2_bagfile_information": {"version": 5}
        }

    @pytest.mark.skipif(not _HAS_PYARROW, reason="pyarrow not installed")
    def test_convert_with_spec_preserves_schema_metadata_in_manifest(self, tmp_bag_file, tmp_path):
        from hephaes.converter import Converter

        spec = ConversionSpec(
            schema=SchemaSpec(name="demo_schema", version=7),
            mapping=self._make_mapping(),
            output=OutputSpec(format="parquet"),
        )
        mock_reader = make_mock_any_reader_with_payloads(
            topics={"/cmd_vel": "geometry_msgs/Twist"},
            messages=[("/cmd_vel", 1_000_000_000, {"v": 1})],
        )

        with _patch_any_reader(mock_reader):
            converter = Converter(
                [str(tmp_bag_file)],
                None,
                tmp_path,
                spec=spec,
                max_workers=1,
            )
            results = converter.convert()

        manifest = json.loads(results[0].with_suffix(".manifest.json").read_text())
        assert manifest["conversion"]["schema"] == {
            "name": "demo_schema",
            "version": 7,
        }

    def test_convert_can_disable_manifest_writes(self, tmp_bag_file, tmp_path):
        from hephaes.converter import Converter

        mock_reader = make_mock_any_reader_with_payloads(
            topics={"/cmd_vel": "geometry_msgs/Twist"},
            messages=[("/cmd_vel", 1_000_000_000, {"v": 1})],
        )
        with _patch_any_reader(mock_reader):
            converter = Converter(
                [str(tmp_bag_file)],
                self._make_mapping(),
                tmp_path,
                max_workers=1,
                output="tfrecord",
                write_manifest=False,
            )
            results = converter.convert()

        assert results[0].exists()
        assert not results[0].with_suffix(".manifest.json").exists()

    def test_convert_tfrecord_no_resample_uses_union_timestamps_with_nulls(self, tmp_bag_file, tmp_path):
        from hephaes.converter import Converter
        from hephaes.tfrecord import stream_tfrecord_rows

        mapping = MappingTemplate.model_validate({"cmd_vel": ["/cmd_vel"], "odom": ["/odom"]})
        mock_reader = make_mock_any_reader_with_payloads(
            topics={"/cmd_vel": "geometry_msgs/Twist", "/odom": "nav_msgs/Odometry"},
            messages=[
                ("/cmd_vel", 1_000_000_000, {"v": 1}),
                ("/odom", 2_000_000_000, {"pose": {"x": 3}}),
            ],
        )

        with _patch_any_reader(mock_reader):
            converter = Converter(
                [str(tmp_bag_file)],
                mapping,
                tmp_path,
                max_workers=1,
                output=TFRecordOutputConfig(),
            )
            results = converter.convert()

        rows = list(stream_tfrecord_rows(results[0]))
        assert [row["timestamp_ns"] for row in rows] == [1_000_000_000, 2_000_000_000]
        assert rows[0]["cmd_vel__present"] == 1
        assert rows[0]["cmd_vel__v"] == 1
        assert rows[0]["odom__present"] == 0
        assert rows[1]["cmd_vel__present"] == 0
        assert rows[1]["odom__present"] == 1
        assert rows[1]["odom__pose__x"] == 3

    @pytest.mark.skipif(not _HAS_PYARROW, reason="pyarrow not installed")
    def test_convert_mapping_alias_fallback(self, tmp_bag_file, tmp_path):
        from hephaes.parquet import stream_wide_parquet_rows

        mapping = MappingTemplate.model_validate({"vel": ["/missing", "/alt_cmd"]})
        mock_reader = make_mock_any_reader_with_payloads(
            topics={"/alt_cmd": "geometry_msgs/Twist"},
            messages=[("/alt_cmd", 1_000_000_000, {"v": 1})],
        )

        with _patch_any_reader(mock_reader):
            from hephaes.converter import Converter

            converter = Converter([str(tmp_bag_file)], mapping, tmp_path, max_workers=1)
            results = converter.convert()

        rows = list(stream_wide_parquet_rows(results[0]))
        assert len(rows) == 1
        assert rows[0]["vel"] is not None

    @pytest.mark.skipif(not _HAS_PYARROW, reason="pyarrow not installed")
    def test_convert_downsample_uses_bucket_latest(self, tmp_bag_file, tmp_path):
        from hephaes.parquet import stream_wide_parquet_rows
        from hephaes.converter import Converter

        mapping = MappingTemplate.model_validate({"cmd_vel": ["/cmd_vel"]})
        mock_reader = make_mock_any_reader_with_payloads(
            topics={"/cmd_vel": "geometry_msgs/Twist"},
            messages=[
                ("/cmd_vel", 0, {"v": 1}),
                ("/cmd_vel", 100_000_000, {"v": 2}),
                ("/cmd_vel", 700_000_000, {"v": 3}),
            ],
        )

        with _patch_any_reader(mock_reader):
            converter = Converter(
                [str(tmp_bag_file)],
                mapping,
                tmp_path,
                max_workers=1,
                resample=ResampleConfig(freq_hz=2.0, method="downsample"),
            )
            results = converter.convert()

        rows = list(stream_wide_parquet_rows(results[0]))
        assert [row["timestamp_ns"] for row in rows] == [0, 500_000_000]

        decoded0 = base64.b64decode(json.loads(rows[0]["cmd_vel"])["value"])
        decoded1 = base64.b64decode(json.loads(rows[1]["cmd_vel"])["value"])
        assert decoded0 == b"raw-1"
        assert decoded1 == b"raw-2"

    @pytest.mark.skipif(not _HAS_PYARROW, reason="pyarrow not installed")
    def test_convert_interpolate_generates_regular_grid(self, tmp_bag_file, tmp_path):
        from hephaes.parquet import stream_wide_parquet_rows
        from hephaes.converter import Converter

        mapping = MappingTemplate.model_validate({"cmd_vel": ["/cmd_vel"]})
        mock_reader = make_mock_any_reader_with_payloads(
            topics={"/cmd_vel": "geometry_msgs/Twist"},
            messages=[
                ("/cmd_vel", 0, {"x": 0.0}),
                ("/cmd_vel", 1_000_000_000, {"x": 2.0}),
            ],
        )

        with _patch_any_reader(mock_reader):
            converter = Converter(
                [str(tmp_bag_file)],
                mapping,
                tmp_path,
                max_workers=1,
                resample=ResampleConfig(freq_hz=2.0, method="interpolate"),
            )
            results = converter.convert()

        rows = list(stream_wide_parquet_rows(results[0]))
        timestamps = [row["timestamp_ns"] for row in rows]
        assert timestamps == [0, 500_000_000, 1_000_000_000]

        middle = json.loads(rows[1]["cmd_vel"])
        assert middle["x"] == pytest.approx(1.0)

    def test_convert_empty_mapping_topics_raises(self, tmp_bag_file, tmp_path):
        from hephaes.converter import Converter

        empty_mapping = MappingTemplate.model_validate({})
        converter = Converter([str(tmp_bag_file)], empty_mapping, tmp_path, max_workers=1)
        with pytest.raises(ValueError, match="No topics found"):
            converter.convert()

    def test_convert_no_matching_topics_raises(self, tmp_bag_file, tmp_path):
        mock_reader = make_mock_any_reader_with_payloads(
            topics={"/odom": "nav_msgs/Odometry"},
            messages=[],
        )
        with _patch_any_reader(mock_reader):
            from hephaes.converter import Converter

            mapping = MappingTemplate.model_validate({"cmd_vel": ["/cmd_vel"]})
            converter = Converter([str(tmp_bag_file)], mapping, tmp_path, max_workers=1)
            with pytest.raises(ValueError, match="No requested topics"):
                converter.convert()
