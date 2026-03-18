"""Tests for hephaes._utils."""
import struct
from pathlib import Path

import pytest

from hephaes._utils import (
    compute_path_size_bytes,
    detect_compression_format,
    determine_ros_version_from_path,
    determine_storage_format_from_path,
    timestamp_to_iso,
)


# ---------------------------------------------------------------------------
# determine_ros_version_from_path
# ---------------------------------------------------------------------------

class TestDetermineRosVersionFromPath:
    def test_bag_returns_ros1(self, tmp_path):
        p = tmp_path / "test.bag"
        p.write_bytes(b"")
        assert determine_ros_version_from_path(str(p)) == "ROS1"

    def test_mcap_returns_ros2(self, tmp_path):
        p = tmp_path / "test.mcap"
        p.write_bytes(b"")
        assert determine_ros_version_from_path(str(p)) == "ROS2"

    def test_path_object_accepted(self, tmp_path):
        p = tmp_path / "test.bag"
        p.write_bytes(b"")
        assert determine_ros_version_from_path(p) == "ROS1"

    def test_uppercase_extension_accepted(self, tmp_path):
        p = tmp_path / "test.BAG"
        p.write_bytes(b"")
        assert determine_ros_version_from_path(p) == "ROS1"

    def test_directory_raises(self, tmp_path):
        with pytest.raises(ValueError, match="must be a file path"):
            determine_ros_version_from_path(tmp_path)

    def test_unsupported_extension_raises(self, tmp_path):
        p = tmp_path / "test.txt"
        p.write_bytes(b"")
        with pytest.raises(ValueError, match="Unsupported bag format"):
            determine_ros_version_from_path(p)


# ---------------------------------------------------------------------------
# determine_storage_format_from_path
# ---------------------------------------------------------------------------

class TestDetermineStorageFormatFromPath:
    def test_bag_returns_bag(self, tmp_path):
        p = tmp_path / "test.bag"
        assert determine_storage_format_from_path(str(p)) == "bag"

    def test_mcap_returns_mcap(self, tmp_path):
        p = tmp_path / "test.mcap"
        assert determine_storage_format_from_path(str(p)) == "mcap"

    def test_uppercase_extension(self, tmp_path):
        p = tmp_path / "test.MCAP"
        assert determine_storage_format_from_path(p) == "mcap"

    def test_unsupported_extension_raises(self):
        with pytest.raises(ValueError, match="Unsupported storage format"):
            determine_storage_format_from_path("/data/file.csv")


# ---------------------------------------------------------------------------
# compute_path_size_bytes
# ---------------------------------------------------------------------------

class TestComputePathSizeBytes:
    def test_existing_file(self, tmp_path):
        p = tmp_path / "file.bag"
        p.write_bytes(b"hello")
        assert compute_path_size_bytes(p) == 5

    def test_nonexistent_file_returns_zero(self, tmp_path):
        p = tmp_path / "missing.bag"
        assert compute_path_size_bytes(p) == 0

    def test_directory_raises(self, tmp_path):
        with pytest.raises(ValueError):
            compute_path_size_bytes(tmp_path)

    def test_string_path_accepted(self, tmp_path):
        p = tmp_path / "file.bag"
        p.write_bytes(b"ab")
        assert compute_path_size_bytes(str(p)) == 2


# ---------------------------------------------------------------------------
# detect_compression_format
# ---------------------------------------------------------------------------

class TestDetectCompressionFormat:
    def test_zstd_magic(self, tmp_path):
        p = tmp_path / "file.zst"
        p.write_bytes(b"\x28\xb5\x2f\xfd" + b"\x00" * 12)
        assert detect_compression_format(p) == "zstd"

    def test_lz4_magic(self, tmp_path):
        p = tmp_path / "file.lz4"
        p.write_bytes(b"\x04\x22\x4d\x18" + b"\x00" * 12)
        assert detect_compression_format(p) == "lz4"

    def test_bz2_magic(self, tmp_path):
        p = tmp_path / "file.bz2"
        p.write_bytes(b"BZ" + b"\x00" * 14)
        assert detect_compression_format(p) == "bz2"

    def test_uncompressed_returns_none(self, tmp_path):
        p = tmp_path / "file.bag"
        p.write_bytes(b"\x00" * 16)
        assert detect_compression_format(p) == "none"

    def test_missing_file_returns_unknown(self, tmp_path):
        p = tmp_path / "missing.bag"
        assert detect_compression_format(p) == "unknown"

    def test_string_path_accepted(self, tmp_path):
        p = tmp_path / "file.bag"
        p.write_bytes(b"\x00" * 16)
        assert detect_compression_format(str(p)) == "none"


# ---------------------------------------------------------------------------
# timestamp_to_iso
# ---------------------------------------------------------------------------

class TestTimestampToIso:
    def test_epoch_zero(self):
        assert timestamp_to_iso(0) == "1970-01-01T00:00:00Z"

    def test_one_second(self):
        assert timestamp_to_iso(1_000_000_000) == "1970-01-01T00:00:01Z"

    def test_fractional_second(self):
        result = timestamp_to_iso(1_500_000_000)
        assert result.endswith("Z")
        assert "1970-01-01T00:00:01" in result

    def test_large_timestamp(self):
        # 2020-01-01 00:00:00 UTC = 1577836800 seconds
        ts_ns = 1_577_836_800 * 1_000_000_000
        result = timestamp_to_iso(ts_ns)
        assert "2020-01-01T00:00:00Z" == result
