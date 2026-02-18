"""Tests for hephaes_core.parquet (ParquetWriter, stream_parquet_rows)."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pyarrow")


# ---------------------------------------------------------------------------
# ParquetWriter
# ---------------------------------------------------------------------------

class TestParquetWriter:
    def test_creates_parquet_file(self, tmp_path):
        from hephaes_core.parquet import ParquetWriter
        with ParquetWriter(output_dir=tmp_path, episode_id="ep001") as writer:
            pass
        assert (tmp_path / "ep001.parquet").exists()

    def test_path_attribute(self, tmp_path):
        from hephaes_core.parquet import ParquetWriter
        with ParquetWriter(output_dir=tmp_path, episode_id="ep001") as writer:
            assert writer.path == tmp_path / "ep001.parquet"

    def test_creates_output_dir_if_missing(self, tmp_path):
        from hephaes_core.parquet import ParquetWriter
        nested = tmp_path / "a" / "b" / "c"
        with ParquetWriter(output_dir=nested, episode_id="ep1") as writer:
            pass
        assert nested.exists()

    def test_write_batch_creates_readable_file(self, tmp_path):
        from hephaes_core.parquet import ParquetWriter
        with ParquetWriter(output_dir=tmp_path, episode_id="ep1") as writer:
            writer.write_batch(
                bag_path="/data/test.bag",
                ros_version="ROS1",
                message_indices=[0, 1],
                timestamps=[1_000_000_000, 2_000_000_000],
                topic_names=["/cmd_vel", "/cmd_vel"],
                mapped_fields=["cmd_vel", "cmd_vel"],
                topic_types=["geometry_msgs/Twist", "geometry_msgs/Twist"],
                payload_json=['{"v": 1}', '{"v": 2}'],
            )
        assert (tmp_path / "ep1.parquet").stat().st_size > 0

    def test_write_empty_batch_no_op(self, tmp_path):
        from hephaes_core.parquet import ParquetWriter
        with ParquetWriter(output_dir=tmp_path, episode_id="ep1") as writer:
            # Should not raise
            writer.write_batch(
                bag_path="/data/test.bag",
                ros_version="ROS1",
                message_indices=[],
                timestamps=[],
                topic_names=[],
                mapped_fields=[],
                topic_types=[],
                payload_json=[],
            )

    def test_context_manager_closes_writer(self, tmp_path):
        from hephaes_core.parquet import ParquetWriter
        writer = ParquetWriter(output_dir=tmp_path, episode_id="ep1")
        writer.__enter__()
        writer.__exit__(None, None, None)
        # File should be properly written/closed
        assert (tmp_path / "ep1.parquet").exists()

    def test_multiple_batches(self, tmp_path):
        from hephaes_core.parquet import ParquetWriter, stream_parquet_rows
        with ParquetWriter(output_dir=tmp_path, episode_id="ep1") as writer:
            for i in range(3):
                writer.write_batch(
                    bag_path="/data/test.bag",
                    ros_version="ROS1",
                    message_indices=[i],
                    timestamps=[i * 1_000_000_000],
                    topic_names=["/t"],
                    mapped_fields=["t"],
                    topic_types=["std_msgs/String"],
                    payload_json=[f'{{"i": {i}}}'],
                )
        rows = list(stream_parquet_rows(tmp_path / "ep1.parquet"))
        assert len(rows) == 3


# ---------------------------------------------------------------------------
# stream_parquet_rows
# ---------------------------------------------------------------------------

class TestStreamParquetRows:
    def _write_test_file(self, path: Path, n_rows: int = 5) -> Path:
        from hephaes_core.parquet import ParquetWriter
        out = path / "test.parquet"
        with ParquetWriter(output_dir=path, episode_id="test") as writer:
            writer.write_batch(
                bag_path="/data/test.bag",
                ros_version="ROS1",
                message_indices=list(range(n_rows)),
                timestamps=[i * 1_000_000_000 for i in range(n_rows)],
                topic_names=["/t"] * n_rows,
                mapped_fields=["t"] * n_rows,
                topic_types=["std_msgs/String"] * n_rows,
                payload_json=[f'{{"i": {i}}}' for i in range(n_rows)],
            )
        return path / "test.parquet"

    def test_yields_all_rows(self, tmp_path):
        from hephaes_core.parquet import stream_parquet_rows
        parquet_file = self._write_test_file(tmp_path, n_rows=5)
        rows = list(stream_parquet_rows(parquet_file))
        assert len(rows) == 5

    def test_row_contains_expected_keys(self, tmp_path):
        from hephaes_core.parquet import stream_parquet_rows
        parquet_file = self._write_test_file(tmp_path, n_rows=1)
        rows = list(stream_parquet_rows(parquet_file))
        row = rows[0]
        assert "episode_id" in row
        assert "bag_path" in row
        assert "timestamp_ns" in row
        assert "data_json" in row

    def test_row_values_correct(self, tmp_path):
        from hephaes_core.parquet import stream_parquet_rows
        parquet_file = self._write_test_file(tmp_path, n_rows=1)
        rows = list(stream_parquet_rows(parquet_file))
        assert rows[0]["episode_id"] == "test"
        assert rows[0]["bag_path"] == "/data/test.bag"
        assert rows[0]["ros_version"] == "ROS1"

    def test_batch_size_respected(self, tmp_path):
        from hephaes_core.parquet import stream_parquet_rows
        parquet_file = self._write_test_file(tmp_path, n_rows=10)
        rows = list(stream_parquet_rows(parquet_file, batch_size=3))
        assert len(rows) == 10

    def test_invalid_batch_size_raises(self, tmp_path):
        from hephaes_core.parquet import stream_parquet_rows
        parquet_file = self._write_test_file(tmp_path, n_rows=1)
        with pytest.raises(ValueError, match="batch_size"):
            list(stream_parquet_rows(parquet_file, batch_size=0))

    def test_column_selection(self, tmp_path):
        from hephaes_core.parquet import stream_parquet_rows
        parquet_file = self._write_test_file(tmp_path, n_rows=2)
        rows = list(stream_parquet_rows(parquet_file, columns=["episode_id", "topic"]))
        assert len(rows) == 2
        for row in rows:
            assert set(row.keys()) == {"episode_id", "topic"}

    def test_string_path_accepted(self, tmp_path):
        from hephaes_core.parquet import stream_parquet_rows
        parquet_file = self._write_test_file(tmp_path, n_rows=2)
        rows = list(stream_parquet_rows(str(parquet_file)))
        assert len(rows) == 2
