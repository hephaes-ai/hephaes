"""Tests for hephaes.parquet helpers and streaming utilities."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

pytest.importorskip("pyarrow")


# ---------------------------------------------------------------------------
# WideParquetWriter
# ---------------------------------------------------------------------------

class TestWideParquetWriter:
    def test_creates_parquet_file(self, tmp_path):
        from hephaes.parquet import WideParquetWriter
        with WideParquetWriter(output_dir=tmp_path, episode_id="ep001", field_names=["cmd_vel"]) as writer:
            pass
        assert (tmp_path / "ep001.parquet").exists()

    def test_path_attribute(self, tmp_path):
        from hephaes.parquet import WideParquetWriter
        with WideParquetWriter(output_dir=tmp_path, episode_id="ep001", field_names=["cmd_vel"]) as writer:
            assert writer.path == tmp_path / "ep001.parquet"

    def test_creates_output_dir_if_missing(self, tmp_path):
        from hephaes.parquet import WideParquetWriter
        nested = tmp_path / "a" / "b" / "c"
        with WideParquetWriter(output_dir=nested, episode_id="ep1", field_names=["f"]) as writer:
            pass
        assert nested.exists()

    def test_schema_has_dynamic_columns(self, tmp_path):
        import pyarrow.parquet as pq
        from hephaes.parquet import WideParquetWriter
        field_names = ["cmd_vel", "odom", "lidar"]
        with WideParquetWriter(output_dir=tmp_path, episode_id="ep1", field_names=field_names) as writer:
            writer.write_table(
                timestamps=[1_000_000_000],
                field_data={"cmd_vel": ['{"x": 1}'], "odom": [None], "lidar": [None]},
            )
        schema = pq.read_schema(str(tmp_path / "ep1.parquet"))
        col_names = schema.names
        assert "timestamp_ns" in col_names
        assert "episode_id" not in col_names
        assert "bag_path" not in col_names
        assert "ros_version" not in col_names
        for fname in field_names:
            assert fname in col_names

    def test_write_table_populates_correct_columns(self, tmp_path):
        from hephaes.parquet import WideParquetWriter, stream_wide_parquet_rows
        with WideParquetWriter(output_dir=tmp_path, episode_id="ep1", field_names=["cmd_vel", "odom"]) as writer:
            writer.write_table(
                timestamps=[1_000_000_000, 2_000_000_000],
                field_data={
                    "cmd_vel": ['{"v": 1}', None],
                    "odom": [None, '{"p": 2}'],
                },
            )
        rows = list(stream_wide_parquet_rows(tmp_path / "ep1.parquet"))
        assert len(rows) == 2
        assert rows[0]["cmd_vel"] == '{"v": 1}'
        assert rows[0]["odom"] is None
        assert rows[1]["cmd_vel"] is None
        assert rows[1]["odom"] == '{"p": 2}'

    def test_write_table_empty_no_op(self, tmp_path):
        from hephaes.parquet import WideParquetWriter
        with WideParquetWriter(output_dir=tmp_path, episode_id="ep1", field_names=["f"]) as writer:
            writer.write_table(
                timestamps=[],
                field_data={},
            )

    def test_absent_field_in_field_data_becomes_all_null(self, tmp_path):
        from hephaes.parquet import WideParquetWriter, stream_wide_parquet_rows
        with WideParquetWriter(output_dir=tmp_path, episode_id="ep1", field_names=["cmd_vel", "odom"]) as writer:
            writer.write_table(
                timestamps=[1_000_000_000, 2_000_000_000],
                field_data={"cmd_vel": ['{"v": 1}', '{"v": 2}']},
                # "odom" absent from field_data
            )
        rows = list(stream_wide_parquet_rows(tmp_path / "ep1.parquet"))
        assert rows[0]["odom"] is None
        assert rows[1]["odom"] is None

    def test_context_manager_closes_writer(self, tmp_path):
        from hephaes.parquet import WideParquetWriter
        writer = WideParquetWriter(output_dir=tmp_path, episode_id="ep1", field_names=["f"])
        writer.__enter__()
        writer.__exit__(None, None, None)
        assert (tmp_path / "ep1.parquet").exists()

    def test_fixed_columns_correct(self, tmp_path):
        from hephaes.parquet import WideParquetWriter, stream_wide_parquet_rows
        with WideParquetWriter(output_dir=tmp_path, episode_id="myep", field_names=["f"]) as writer:
            writer.write_table(
                timestamps=[999],
                field_data={"f": ['{}']},
            )
        rows = list(stream_wide_parquet_rows(tmp_path / "myep.parquet"))
        assert rows[0]["timestamp_ns"] == 999


# ---------------------------------------------------------------------------
# stream_wide_parquet_rows
# ---------------------------------------------------------------------------

class TestStreamWideParquetRows:
    def _write_test_file(self, path: Path, n_rows: int = 5) -> Path:
        from hephaes.parquet import WideParquetWriter
        with WideParquetWriter(output_dir=path, episode_id="test", field_names=["f"]) as writer:
            writer.write_table(
                timestamps=[i * 1_000_000_000 for i in range(n_rows)],
                field_data={"f": [f'{{"i": {i}}}' for i in range(n_rows)]},
            )
        return path / "test.parquet"

    def test_yields_all_rows(self, tmp_path):
        from hephaes.parquet import stream_wide_parquet_rows
        parquet_file = self._write_test_file(tmp_path, n_rows=5)
        rows = list(stream_wide_parquet_rows(parquet_file))
        assert len(rows) == 5

    def test_row_contains_expected_keys(self, tmp_path):
        from hephaes.parquet import stream_wide_parquet_rows
        parquet_file = self._write_test_file(tmp_path, n_rows=1)
        rows = list(stream_wide_parquet_rows(parquet_file))
        row = rows[0]
        assert "timestamp_ns" in row
        assert "f" in row

    def test_null_field_is_none_in_dict(self, tmp_path):
        from hephaes.parquet import WideParquetWriter, stream_wide_parquet_rows
        with WideParquetWriter(output_dir=tmp_path, episode_id="ep", field_names=["a", "b"]) as w:
            w.write_table(
                timestamps=[1],
                field_data={"a": ["{}"], "b": [None]},
            )
        rows = list(stream_wide_parquet_rows(tmp_path / "ep.parquet"))
        assert rows[0]["b"] is None

    def test_batch_size_respected(self, tmp_path):
        from hephaes.parquet import stream_wide_parquet_rows
        parquet_file = self._write_test_file(tmp_path, n_rows=10)
        rows = list(stream_wide_parquet_rows(parquet_file, batch_size=3))
        assert len(rows) == 10

    def test_invalid_batch_size_raises(self, tmp_path):
        from hephaes.parquet import stream_wide_parquet_rows
        parquet_file = self._write_test_file(tmp_path, n_rows=1)
        with pytest.raises(ValueError, match="batch_size"):
            list(stream_wide_parquet_rows(parquet_file, batch_size=0))

    def test_column_selection(self, tmp_path):
        from hephaes.parquet import stream_wide_parquet_rows
        parquet_file = self._write_test_file(tmp_path, n_rows=2)
        rows = list(stream_wide_parquet_rows(parquet_file, columns=["timestamp_ns"]))
        assert len(rows) == 2
        for row in rows:
            assert set(row.keys()) == {"timestamp_ns"}

    def test_string_path_accepted(self, tmp_path):
        from hephaes.parquet import stream_wide_parquet_rows
        parquet_file = self._write_test_file(tmp_path, n_rows=2)
        rows = list(stream_wide_parquet_rows(str(parquet_file)))
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# extract_images
# ---------------------------------------------------------------------------

class TestExtractImages:
    @staticmethod
    def _encoded_bytes(payload: bytes) -> str:
        return json.dumps(
            {
                "__bytes__": True,
                "encoding": "base64",
                "value": base64.b64encode(payload).decode("ascii"),
            }
        )

    def test_extracts_base64_payloads_from_column(self, tmp_path):
        from hephaes.parquet import WideParquetWriter, extract_images

        img0 = b"\x89PNG\r\n\x1a\nimg0"
        img1 = b"\x89PNG\r\n\x1a\nimg1"

        with WideParquetWriter(output_dir=tmp_path, episode_id="ep", field_names=["camera"]) as writer:
            writer.write_table(
                timestamps=[1, 2],
                field_data={
                    "camera": [
                        self._encoded_bytes(img0),
                        self._encoded_bytes(img1),
                    ]
                },
            )

        images = extract_images(tmp_path / "ep.parquet", "camera")
        assert images == [img0, img1]

    def test_extracts_nested_base64_payloads(self, tmp_path):
        from hephaes.parquet import WideParquetWriter, extract_images

        image_payload = b"\xff\xd8\xffjpeg"
        nested = json.dumps(
            {
                "header": {"frame_id": "cam"},
                "data": {
                    "__bytes__": True,
                    "encoding": "base64",
                    "value": base64.b64encode(image_payload).decode("ascii"),
                },
            }
        )

        with WideParquetWriter(output_dir=tmp_path, episode_id="nested", field_names=["camera"]) as writer:
            writer.write_table(
                timestamps=[1],
                field_data={"camera": [nested]},
            )

        images = extract_images(tmp_path / "nested.parquet", "camera")
        assert images == [image_payload]

    def test_missing_column_raises(self, tmp_path):
        from hephaes.parquet import WideParquetWriter, extract_images

        with WideParquetWriter(output_dir=tmp_path, episode_id="ep", field_names=["camera"]) as writer:
            writer.write_table(
                timestamps=[1],
                field_data={"camera": [self._encoded_bytes(b"img")]},
            )

        with pytest.raises(ValueError, match="not found"):
            extract_images(tmp_path / "ep.parquet", "missing")
