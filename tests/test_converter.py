"""Tests for hephaes_core.converter."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from conftest import make_mock_any_reader
from hephaes_core.converter import _json_default, _resolve_mapping_for_bag
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
        # If first source topic not available, falls back to second
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

    def test_init_unsupported_format_raises(self, tmp_bag_file, tmp_path):
        from hephaes_core.converter import Converter
        with pytest.raises(ValueError, match="Unsupported output format"):
            Converter([str(tmp_bag_file)], self._make_mapping(), tmp_path, output_format="csv")

    def test_init_batch_size_zero_raises(self, tmp_bag_file, tmp_path):
        from hephaes_core.converter import Converter
        with pytest.raises(ValueError, match="batch_size"):
            Converter([str(tmp_bag_file)], self._make_mapping(), tmp_path, batch_size=0)

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
