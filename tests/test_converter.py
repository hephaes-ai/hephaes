"""Tests for hephaes_core.converter."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from conftest import make_mock_any_reader
from hephaes_core.converter import (
    _build_time_grid,
    _interpolate_json_leaves,
    _json_default,
    _resolve_mapping_for_bag,
    _resample_field,
    _TopicBuffer,
)
from hephaes_core.models import MappingTemplate

_HAS_PYARROW = importlib.util.find_spec("pyarrow") is not None


def _patch_any_reader(mock_reader):
    return patch("hephaes_core.reader.AnyReader", return_value=mock_reader)


# ---------------------------------------------------------------------------
# _json_default
# ---------------------------------------------------------------------------

class TestJsonDefault:
    def test_bytes_encoded_as_base64(self):
        result = _json_default(b"\x00\x01\x02")
        assert result["__bytes__"] is True
        assert result["encoding"] == "base64"
        assert "value" in result

    def test_bytearray_encoded(self):
        result = _json_default(bytearray(b"hello"))
        assert result["__bytes__"] is True

    def test_set_converted_to_list(self):
        result = _json_default({1, 2, 3})
        assert isinstance(result, list)
        assert sorted(result) == [1, 2, 3]

    def test_dataclass_converted_to_dict(self):
        from dataclasses import dataclass

        @dataclass
        class Point:
            x: float
            y: float

        result = _json_default(Point(1.0, 2.0))
        assert result == {"x": 1.0, "y": 2.0}

    def test_object_with_dict_attr(self):
        class Obj:
            def __init__(self):
                self.value = 42

        result = _json_default(Obj())
        assert result == {"value": 42}

    def test_fallback_to_str(self):
        class NoDict:
            __slots__ = ()

            def __str__(self):
                return "custom_str"

        result = _json_default(NoDict())
        assert result == "custom_str"


# ---------------------------------------------------------------------------
# _resolve_mapping_for_bag
# ---------------------------------------------------------------------------

class TestResolveMappingForBag:
    def test_matching_topic(self):
        mapping = MappingTemplate.model_validate({"cmd_vel": ["/cmd_vel"]})
        topics_to_read, rename_map = _resolve_mapping_for_bag(
            mapping=mapping,
            available_topics={"/cmd_vel": "geometry_msgs/Twist"},
            requested_topics={"/cmd_vel"},
        )
        assert "/cmd_vel" in topics_to_read
        assert rename_map["/cmd_vel"] == "cmd_vel"

    def test_fallback_source_topic(self):
        mapping = MappingTemplate.model_validate({"vel": ["/missing", "/cmd_vel"]})
        topics_to_read, rename_map = _resolve_mapping_for_bag(
            mapping=mapping,
            available_topics={"/cmd_vel": "geometry_msgs/Twist"},
            requested_topics={"/missing", "/cmd_vel"},
        )
        assert "/cmd_vel" in topics_to_read
        assert rename_map["/cmd_vel"] == "vel"

    def test_topic_not_in_available_skipped(self):
        mapping = MappingTemplate.model_validate({"field": ["/nonexistent"]})
        topics_to_read, rename_map = _resolve_mapping_for_bag(
            mapping=mapping,
            available_topics={"/cmd_vel": "geometry_msgs/Twist"},
            requested_topics={"/nonexistent"},
        )
        assert topics_to_read == []
        assert rename_map == {}

    def test_topic_not_in_requested_skipped(self):
        mapping = MappingTemplate.model_validate({"cmd_vel": ["/cmd_vel"]})
        topics_to_read, rename_map = _resolve_mapping_for_bag(
            mapping=mapping,
            available_topics={"/cmd_vel": "geometry_msgs/Twist"},
            requested_topics=set(),
        )
        assert topics_to_read == []


# ---------------------------------------------------------------------------
# _build_time_grid
# ---------------------------------------------------------------------------

class TestBuildTimeGrid:
    def _make_buffers(self, data: dict[str, list[int]]) -> dict[str, _TopicBuffer]:
        buffers = {}
        for name, timestamps in data.items():
            buf = _TopicBuffer()
            for ts in timestamps:
                buf.append(ts, "{}")
            buffers[name] = buf
        return buffers

    def test_no_resample_union_of_all_timestamps(self):
        buffers = self._make_buffers({"a": [1000, 3000], "b": [2000, 4000]})
        grid = _build_time_grid(topic_buffers=buffers, resample_freq_hz=None)
        assert grid == [1000, 2000, 3000, 4000]

    def test_no_resample_deduplicates(self):
        buffers = self._make_buffers({"a": [1000, 2000], "b": [1000, 3000]})
        grid = _build_time_grid(topic_buffers=buffers, resample_freq_hz=None)
        assert grid == [1000, 2000, 3000]

    def test_resample_regular_grid(self):
        # 10 Hz → step = 100_000_000 ns
        buffers = self._make_buffers({"a": [0, 300_000_000]})
        grid = _build_time_grid(topic_buffers=buffers, resample_freq_hz=10.0)
        step = 100_000_000
        assert grid[0] == 0
        assert all(grid[i + 1] - grid[i] == step for i in range(len(grid) - 1))
        assert grid[-1] <= 300_000_000

    def test_empty_buffers_returns_empty(self):
        grid = _build_time_grid(topic_buffers={}, resample_freq_hz=None)
        assert grid == []

    def test_single_message_no_resample(self):
        buffers = self._make_buffers({"a": [42]})
        grid = _build_time_grid(topic_buffers=buffers, resample_freq_hz=None)
        assert grid == [42]


# ---------------------------------------------------------------------------
# _resample_field
# ---------------------------------------------------------------------------

class TestResampleField:
    def _make_buf(self, ts_payload: list[tuple[int, str]]) -> _TopicBuffer:
        buf = _TopicBuffer()
        for ts, p in ts_payload:
            buf.append(ts, p)
        return buf

    class _DummySerializer:
        def dumps(self, obj):
            return json.dumps(obj)

    def test_ffill_before_first_message_is_null(self):
        buf = self._make_buf([(2000, '{"v": 1}')
        ])
        result = _resample_field(buf=buf, grid=[1000, 2000], method="ffill", serializer=self._DummySerializer())
        assert result[0] is None
        assert result[1] == '{"v": 1}'

    def test_ffill_carries_forward(self):
        buf = self._make_buf([(1000, '{"v": 1}'), (3000, '{"v": 2}')])
        result = _resample_field(buf=buf, grid=[1000, 2000, 3000], method="ffill", serializer=self._DummySerializer())
        assert result == ['{"v": 1}', '{"v": 1}', '{"v": 2}']

    def test_ffill_exact_timestamp_match(self):
        buf = self._make_buf([(1000, '{"v": 99}')
        ])
        result = _resample_field(buf=buf, grid=[1000], method="ffill", serializer=self._DummySerializer())
        assert result == ['{"v": 99}']

    def test_ffill_empty_buffer_all_null(self):
        buf = _TopicBuffer()
        result = _resample_field(buf=buf, grid=[1000, 2000], method="ffill", serializer=self._DummySerializer())
        assert result == [None, None]

    def test_interpolate_numeric_leaves(self):
        buf = self._make_buf([(0, '{"x": 0.0}'), (2000, '{"x": 2.0}')])
        result = _resample_field(buf=buf, grid=[0, 1000, 2000], method="interpolate", serializer=self._DummySerializer())
        mid = json.loads(result[1])
        assert abs(mid["x"] - 1.0) < 1e-9

    def test_interpolate_before_first_is_null(self):
        buf = self._make_buf([(1000, '{"x": 1.0}'), (2000, '{"x": 2.0}')])
        result = _resample_field(buf=buf, grid=[500, 1000], method="interpolate", serializer=self._DummySerializer())
        assert result[0] is None

    def test_interpolate_after_last_forward_fills(self):
        buf = self._make_buf([(1000, '{"x": 5.0}')])
        result = _resample_field(buf=buf, grid=[1000, 2000], method="interpolate", serializer=self._DummySerializer())
        assert result[1] == '{"x": 5.0}'

    def test_interpolate_nonnumeric_forward_fills(self):
        buf = self._make_buf([(0, '{"label": "a"}'), (2000, '{"label": "b"}')])
        result = _resample_field(buf=buf, grid=[0, 1000, 2000], method="interpolate", serializer=self._DummySerializer())
        mid = json.loads(result[1])
        # non-numeric: should forward-fill from lo
        assert mid["label"] == "a"


# ---------------------------------------------------------------------------
# _interpolate_json_leaves
# ---------------------------------------------------------------------------

class TestInterpolateJsonLeaves:
    def test_scalar_numbers(self):
        assert _interpolate_json_leaves(0.0, 4.0, 0.5) == pytest.approx(2.0)

    def test_dict_numeric_leaves(self):
        result = _interpolate_json_leaves({"x": 0.0, "y": 10.0}, {"x": 2.0, "y": 20.0}, 0.5)
        assert result["x"] == pytest.approx(1.0)
        assert result["y"] == pytest.approx(15.0)

    def test_list_numeric_elements(self):
        result = _interpolate_json_leaves([0.0, 10.0], [2.0, 20.0], 0.5)
        assert result == pytest.approx([1.0, 15.0])

    def test_nonnumeric_forward_fills(self):
        result = _interpolate_json_leaves("hello", "world", 0.5)
        assert result == "hello"

    def test_mismatched_list_forward_fills(self):
        result = _interpolate_json_leaves([1, 2], [3, 4, 5], 0.5)
        assert result == [1, 2]

    def test_nested_dict(self):
        lo = {"linear": {"x": 0.0}}
        hi = {"linear": {"x": 2.0}}
        result = _interpolate_json_leaves(lo, hi, 0.5)
        assert result["linear"]["x"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Converter class
# ---------------------------------------------------------------------------

class TestConverter:
    def _make_mapping(self):
        return MappingTemplate.model_validate({"cmd_vel": ["/cmd_vel"]})

    def test_init_not_list_raises(self, tmp_path):
        from hephaes_core.converter import Converter
        with pytest.raises(TypeError, match="must be a list"):
            Converter("not_a_list", self._make_mapping(), tmp_path)

    def test_init_empty_list_raises(self, tmp_path):
        from hephaes_core.converter import Converter
        with pytest.raises(ValueError, match="non-empty"):
            Converter([], self._make_mapping(), tmp_path)

    def test_init_negative_progress_every_raises(self, tmp_bag_file, tmp_path):
        from hephaes_core.converter import Converter
        with pytest.raises(ValueError, match="progress_every"):
            Converter([str(tmp_bag_file)], self._make_mapping(), tmp_path, progress_every=-1)

    def test_init_max_workers_zero_raises(self, tmp_bag_file, tmp_path):
        from hephaes_core.converter import Converter
        with pytest.raises(ValueError, match="max_workers"):
            Converter([str(tmp_bag_file)], self._make_mapping(), tmp_path, max_workers=0)

    def test_init_invalid_bag_extension_raises(self, tmp_path):
        from hephaes_core.converter import Converter
        p = tmp_path / "file.txt"
        p.write_bytes(b"")
        with pytest.raises(ValueError):
            Converter([str(p)], self._make_mapping(), tmp_path)

    def test_init_resample_freq_hz_negative_raises(self, tmp_bag_file, tmp_path):
        from hephaes_core.converter import Converter
        with pytest.raises(ValueError, match="resample_freq_hz"):
            Converter([str(tmp_bag_file)], self._make_mapping(), tmp_path, resample_freq_hz=-1.0)

    def test_init_resample_freq_hz_zero_raises(self, tmp_bag_file, tmp_path):
        from hephaes_core.converter import Converter
        with pytest.raises(ValueError, match="resample_freq_hz"):
            Converter([str(tmp_bag_file)], self._make_mapping(), tmp_path, resample_freq_hz=0.0)

    def test_init_invalid_resample_method_raises(self, tmp_bag_file, tmp_path):
        from hephaes_core.converter import Converter
        with pytest.raises(ValueError, match="resample_method"):
            Converter([str(tmp_bag_file)], self._make_mapping(), tmp_path, resample_method="invalid")  # type: ignore

    def test_init_valid(self, tmp_bag_file, tmp_path):
        from hephaes_core.converter import Converter
        c = Converter([str(tmp_bag_file)], self._make_mapping(), tmp_path)
        assert len(c.file_paths) == 1

    @pytest.mark.skipif(not _HAS_PYARROW, reason="pyarrow not installed")
    def test_convert_returns_parquet_paths(self, tmp_bag_file, tmp_path):
        mock_reader = make_mock_any_reader(
            topics={"/cmd_vel": "geometry_msgs/Twist"},
            messages=[("/cmd_vel", 1_000_000_000, {"v": 1}), ("/cmd_vel", 2_000_000_000, {"v": 2})],
        )
        with _patch_any_reader(mock_reader):
            from hephaes_core.converter import Converter
            c = Converter(
                [str(tmp_bag_file)],
                self._make_mapping(),
                tmp_path,
                max_workers=1,
            )
            results = c.convert()
            assert len(results) == 1
            assert results[0].suffix == ".parquet"
            assert results[0].exists()

    @pytest.mark.skipif(not _HAS_PYARROW, reason="pyarrow not installed")
    def test_convert_wide_schema_has_field_columns(self, tmp_bag_file, tmp_path):
        import pyarrow.parquet as pq
        mock_reader = make_mock_any_reader(
            topics={"/cmd_vel": "geometry_msgs/Twist"},
            messages=[("/cmd_vel", 1_000_000_000, {"v": 1})],
        )
        with _patch_any_reader(mock_reader):
            from hephaes_core.converter import Converter
            mapping = MappingTemplate.model_validate({"cmd_vel": ["/cmd_vel"], "odom": ["/odom"]})
            c = Converter([str(tmp_bag_file)], mapping, tmp_path, max_workers=1)
            results = c.convert()
        schema = pq.read_schema(str(results[0]))
        assert "cmd_vel" in schema.names
        assert "odom" in schema.names

    @pytest.mark.skipif(not _HAS_PYARROW, reason="pyarrow not installed")
    def test_convert_wide_row_count_equals_unique_timestamps(self, tmp_bag_file, tmp_path):
        from hephaes_core.parquet import stream_wide_parquet_rows
        mock_reader = make_mock_any_reader(
            topics={"/cmd_vel": "geometry_msgs/Twist", "/odom": "nav_msgs/Odometry"},
            messages=[
                ("/cmd_vel", 1_000_000_000, {}),
                ("/odom", 2_000_000_000, {}),
                ("/cmd_vel", 3_000_000_000, {}),
            ],
        )
        with _patch_any_reader(mock_reader):
            from hephaes_core.converter import Converter
            mapping = MappingTemplate.model_validate({"cmd_vel": ["/cmd_vel"], "odom": ["/odom"]})
            c = Converter([str(tmp_bag_file)], mapping, tmp_path, max_workers=1)
            results = c.convert()
        rows = list(stream_wide_parquet_rows(results[0]))
        assert len(rows) == 3  # 3 unique timestamps

    @pytest.mark.skipif(not _HAS_PYARROW, reason="pyarrow not installed")
    def test_convert_absent_topic_column_all_null(self, tmp_bag_file, tmp_path):
        from hephaes_core.parquet import stream_wide_parquet_rows
        # mapping has "odom" but bag only has /cmd_vel
        mock_reader = make_mock_any_reader(
            topics={"/cmd_vel": "geometry_msgs/Twist"},
            messages=[("/cmd_vel", 1_000_000_000, {})],
        )
        with _patch_any_reader(mock_reader):
            from hephaes_core.converter import Converter
            mapping = MappingTemplate.model_validate({"cmd_vel": ["/cmd_vel"], "odom": ["/odom"]})
            c = Converter([str(tmp_bag_file)], mapping, tmp_path, max_workers=1)
            results = c.convert()
        rows = list(stream_wide_parquet_rows(results[0]))
        assert all(row["odom"] is None for row in rows)

    @pytest.mark.skipif(not _HAS_PYARROW, reason="pyarrow not installed")
    def test_convert_resample_freq_produces_regular_grid(self, tmp_bag_file, tmp_path):
        from hephaes_core.parquet import stream_wide_parquet_rows
        step_ns = 100_000_000  # 10 Hz
        mock_reader = make_mock_any_reader(
            topics={"/cmd_vel": "geometry_msgs/Twist"},
            messages=[
                ("/cmd_vel", 0, {}),
                ("/cmd_vel", 300_000_000, {}),
            ],
        )
        with _patch_any_reader(mock_reader):
            from hephaes_core.converter import Converter
            c = Converter(
                [str(tmp_bag_file)],
                self._make_mapping(),
                tmp_path,
                max_workers=1,
                resample_freq_hz=10.0,
            )
            results = c.convert()
        rows = list(stream_wide_parquet_rows(results[0]))
        timestamps = [r["timestamp_ns"] for r in rows]
        assert len(timestamps) > 1
        diffs = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        assert all(d == step_ns for d in diffs)

    def test_convert_empty_mapping_topics_raises(self, tmp_bag_file, tmp_path):
        from hephaes_core.converter import Converter
        empty_mapping = MappingTemplate.model_validate({})
        c = Converter([str(tmp_bag_file)], empty_mapping, tmp_path, max_workers=1)
        with pytest.raises(ValueError, match="No topics found"):
            c.convert()

    def test_convert_no_matching_topics_raises(self, tmp_bag_file, tmp_path):
        mock_reader = make_mock_any_reader(
            topics={"/odom": "nav_msgs/Odometry"},
            messages=[],
        )
        with _patch_any_reader(mock_reader):
            from hephaes_core.converter import Converter
            mapping = MappingTemplate.model_validate({"cmd_vel": ["/cmd_vel"]})
            c = Converter([str(tmp_bag_file)], mapping, tmp_path, max_workers=1)
            with pytest.raises(ValueError, match="No requested topics"):
                c.convert()

    def test_derive_topics(self, tmp_bag_file, tmp_path):
        from hephaes_core.converter import Converter
        mapping = MappingTemplate.model_validate({"vel": ["/cmd_vel", "/vel"], "odom": ["/odom"]})
        c = Converter([str(tmp_bag_file)], mapping, tmp_path)
        topics = c._derive_topics()
        assert "/cmd_vel" in topics
        assert "/vel" in topics
        assert "/odom" in topics
        assert len(topics) == len(set(topics))  # No duplicates
