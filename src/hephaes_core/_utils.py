import logging
from datetime import datetime
from datetime import UTC
from pathlib import Path

from .models import RosVersion, StorageFormat

logger = logging.getLogger(__name__)


def determine_ros_version_from_path(path: str | Path) -> RosVersion:
    bag_path = Path(path)
    suffix = bag_path.suffix.lower()

    if bag_path.is_dir():
        raise ValueError(
            f"Bag path '{bag_path}' must be a file path ending in .bag or .mcap. "
            "Directory paths are not supported."
        )

    if suffix == ".bag":
        return "ROS1"
    if suffix == ".mcap":
        return "ROS2"
    raise ValueError(
        f"Unsupported bag format for path '{bag_path}'. "
        "Expected a .bag or .mcap file path."
    )


def determine_storage_format_from_path(path: str | Path) -> StorageFormat:
    suffix = Path(path).suffix.lower()
    if suffix == ".bag":
        return "bag"
    if suffix == ".mcap":
        return "mcap"
    raise ValueError(
        f"Unsupported storage format for path '{path}'. Expected a .bag or .mcap file path."
    )


def compute_path_size_bytes(path: str | Path) -> int:
    bag_path = Path(path)
    if not bag_path.exists():
        return 0
    if bag_path.is_dir():
        raise ValueError(
            f"Bag path '{bag_path}' must be a file path ending in .bag or .mcap. "
            "Directory paths are not supported."
        )
    if bag_path.is_file():
        return bag_path.stat().st_size
    return 0


def detect_compression_format(file_path: Path | str) -> str:
    try:
        with open(file_path, "rb") as handle:
            header = handle.read(16)
            if header.startswith(b"\x28\xb5\x2f\xfd"):
                return "zstd"
            if header.startswith(b"\x04\x22\x4d\x18"):
                return "lz4"
            if header.startswith(b"BZ"):
                return "bz2"
            return "none"
    except Exception as exc:
        logger.warning(
            "Compression detection failed for '%s': %s. Falling back to compression_format='unknown'.",
            file_path,
            exc,
        )
        return "unknown"


def timestamp_to_iso(timestamp_ns: int) -> str:
    timestamp_s = timestamp_ns / 1e9
    dt = datetime.fromtimestamp(timestamp_s, tz=UTC)
    return dt.isoformat().replace("+00:00", "Z")
