import logging
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Generator

import yaml
from rosbags.highlevel import AnyReader

from ._utils import (
    compute_path_size_bytes,
    detect_compression_format,
    determine_ros_version_from_path,
    determine_storage_format_from_path,
)
from .models import InternalStats, Message, ReaderMetadata, RosVersion

logger = logging.getLogger(__name__)


class ReaderRegistry:
    """Registry mapping ROS versions to concrete reader implementations."""

    def __init__(self) -> None:
        self._registry: dict[RosVersion, type["RosReader"]] = {}

    def register(self, ros_version: RosVersion, reader_cls: type["RosReader"]) -> None:
        self._registry[ros_version] = reader_cls

    def resolve(self, ros_version: RosVersion) -> type["RosReader"]:
        try:
            return self._registry[ros_version]
        except KeyError as exc:
            raise ValueError(f"Unsupported ROS version: {ros_version}") from exc


_DEFAULT_READER_REGISTRY = ReaderRegistry()


def register_reader(reader_cls: type["RosReader"]) -> type["RosReader"]:
    _DEFAULT_READER_REGISTRY.register(reader_cls.ROS_VERSION, reader_cls)
    return reader_cls


class RosReader(ABC):
    ROS_VERSION: RosVersion

    @classmethod
    def open(
        cls,
        bag_path: str,
        ros_version: RosVersion | None = None,
        *,
        registry: ReaderRegistry | None = None,
    ) -> "RosReader":
        resolved_ros_version = ros_version or determine_ros_version_from_path(bag_path)
        resolved_registry = registry or _DEFAULT_READER_REGISTRY
        reader_cls = resolved_registry.resolve(resolved_ros_version)
        return reader_cls(bag_path)

    def __init__(self, bag_path: str):
        self.bag_path = Path(bag_path)
        self.ros_version = self.ROS_VERSION
        self._topics: Dict[str, str] = {}
        self._reader: AnyReader | None = None
        self._init_reader()

    @abstractmethod
    def _resolve_reader_paths(self) -> list[Path]:
        """Return resolved bag file paths to pass into AnyReader."""

    @property
    @abstractmethod
    def metadata(self) -> ReaderMetadata:
        ...

    @abstractmethod
    def extract_internal_statistics(self) -> InternalStats:
        ...

    def _init_reader(self) -> None:
        reader_paths = self._resolve_reader_paths()
        self._reader = AnyReader(reader_paths)
        self._reader.open()
        self._scan_topics()

    def _scan_topics(self) -> None:
        reader = self._require_reader()
        for topic, connection in reader.topics.items():
            self._topics[topic] = connection.msgtype

    def _require_reader(self) -> AnyReader:
        if self._reader is None:
            raise RuntimeError("Reader is not initialized")
        return self._reader

    def _build_reader_metadata(
        self,
        *,
        file_path: Path | str,
        source_metadata: dict[str, Any] | None = None,
    ) -> ReaderMetadata:
        resolved_file_path = Path(file_path)
        return ReaderMetadata(
            path=str(self.bag_path),
            file_path=str(resolved_file_path),
            ros_version=self.ros_version,
            storage_format=determine_storage_format_from_path(resolved_file_path),
            file_size_bytes=compute_path_size_bytes(self.bag_path),
            source_metadata=source_metadata,
        )

    @property
    def topics(self) -> Dict[str, str]:
        return self._topics.copy()

    def _safe_reader_int(self, attr_name: str, default: int | None) -> int | None:
        reader = self._require_reader()
        try:
            return int(getattr(reader, attr_name))
        except Exception:
            return default

    @property
    def start_time(self) -> int | None:
        return self._safe_reader_int("start_time", default=None)

    @property
    def end_time(self) -> int | None:
        return self._safe_reader_int("end_time", default=None)

    @property
    def message_count(self) -> int:
        value = self._safe_reader_int("message_count", default=0)
        return value if value is not None else 0

    def iter_message_headers(
        self, topics: list[str] | None = None
    ) -> Generator[tuple[str, int], None, None]:
        """Yield (topic, timestamp) for each message without deserializing the payload.

        Significantly faster than read_messages() when the message body is not needed.
        """
        reader = self._require_reader()
        try:
            if topics:
                target_topics = set(topics)
                connections = [conn for conn in reader.connections if conn.topic in target_topics]
            else:
                connections = reader.connections

            for connection, timestamp, _rawdata in reader.messages(connections=connections):
                yield connection.topic, timestamp
        except Exception as exc:
            raise RuntimeError(f"Failed to read message headers from bag: {exc}") from exc

    def iter_raw_messages(
        self, topics: list[str] | None = None
    ) -> Generator[tuple[str, int, str, bytes], None, None]:
        reader = self._require_reader()
        try:
            if topics:
                target_topics = set(topics)
                connections = [conn for conn in reader.connections if conn.topic in target_topics]
            else:
                connections = reader.connections

            for connection, timestamp, rawdata in reader.messages(connections=connections):
                yield connection.topic, timestamp, connection.msgtype, rawdata
        except Exception as exc:
            raise RuntimeError(f"Failed to read raw messages from bag: {exc}") from exc

    def read_messages(self, topics: list[str] | None = None) -> Generator[Message, None, None]:
        reader = self._require_reader()
        try:
            if topics:
                target_topics = set(topics)
                connections = [conn for conn in reader.connections if conn.topic in target_topics]
            else:
                connections = reader.connections

            for connection, timestamp, rawdata in reader.messages(connections=connections):
                try:
                    msg_data = reader.deserialize(rawdata, connection.msgtype)
                    yield Message(
                        timestamp=timestamp,
                        topic=connection.topic,
                        data=msg_data,
                    )
                except Exception as exc:
                    skip_message = (
                        "Skipping message due to deserialization failure "
                        f"(topic='{connection.topic}', type='{connection.msgtype}', "
                        f"timestamp={timestamp}): {exc}"
                    )
                    print(skip_message, file=sys.stderr)
                    logger.warning(skip_message)
                    continue
        except Exception as exc:
            raise RuntimeError(f"Failed to read messages from bag: {exc}") from exc

    def close(self) -> None:
        if self._reader is not None:
            self._reader.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(path='{self.bag_path}', "
            f"ros_version='{self.ros_version}', "
            f"topics={len(self._topics)})"
        )


@register_reader
class ROS1Reader(RosReader):
    ROS_VERSION = "ROS1"

    def __init__(self, bag_path: str):
        self._resolved_bag_path: Path | None = None
        super().__init__(bag_path)

    def _resolve_reader_paths(self) -> list[Path]:
        if not self.bag_path.exists():
            raise FileNotFoundError(f"Path not found: {self.bag_path}")
        if not self.bag_path.is_file():
            raise ValueError(f"ROS1 path must be a .bag file path: {self.bag_path}")
        if self.bag_path.suffix.lower() != ".bag":
            raise ValueError(f"ROS1 path must end in .bag: {self.bag_path}")

        self._resolved_bag_path = self.bag_path
        return [self.bag_path]

    @property
    def metadata(self) -> ReaderMetadata:
        if self._resolved_bag_path is None:
            raise RuntimeError("ROS1 bag path is not resolved")
        return self._build_reader_metadata(file_path=self._resolved_bag_path)

    def extract_internal_statistics(self) -> InternalStats:
        if self._resolved_bag_path is None:
            return InternalStats(compression_format="unknown")
        return InternalStats(
            compression_format=detect_compression_format(self._resolved_bag_path),
        )


@register_reader
class ROS2Reader(RosReader):
    ROS_VERSION = "ROS2"

    def __init__(self, bag_path: str):
        self._mcap_path: Path | None = None
        self._metadata_path: Path | None = None
        self._source_metadata: dict[str, Any] | None = None
        self._cached_metadata: ReaderMetadata | None = None
        super().__init__(bag_path)

    def _load_source_metadata(self, metadata_path: Path) -> dict[str, Any] | None:
        if not metadata_path.exists():
            return None
        try:
            with open(metadata_path, "r") as handle:
                loaded = yaml.safe_load(handle)
            if isinstance(loaded, dict):
                return loaded
            if loaded is not None:
                return {"metadata_yaml": loaded}
        except Exception as exc:
            logger.warning("Failed to parse metadata.yaml at '%s': %s", metadata_path, exc)
        return None

    def _resolve_reader_paths(self) -> list[Path]:
        if not self.bag_path.exists():
            raise FileNotFoundError(f"Path not found: {self.bag_path}")
        if not self.bag_path.is_file():
            raise ValueError(f"ROS2 path must be a .mcap file path: {self.bag_path}")

        if self.bag_path.suffix.lower() != ".mcap":
            raise ValueError(f"ROS2 path must end in .mcap: {self.bag_path}")
        self._mcap_path = self.bag_path
        self._metadata_path = self.bag_path.parent / "metadata.yaml"
        self._source_metadata = self._load_source_metadata(self._metadata_path)

        if self._mcap_path is None:
            raise RuntimeError("Failed to resolve ROS2 .mcap path")
        return [self._mcap_path]

    @property
    def metadata(self) -> ReaderMetadata:
        if self._cached_metadata is None:
            if self._mcap_path is None:
                raise RuntimeError("ROS2 .mcap path is not resolved")
            if self._source_metadata is None and self._metadata_path is not None:
                self._source_metadata = self._load_source_metadata(self._metadata_path)
            self._cached_metadata = self._build_reader_metadata(
                file_path=self._mcap_path,
                source_metadata=self._source_metadata,
            )
        return self._cached_metadata

    def close(self) -> None:
        try:
            super().close()
        finally:
            self._cached_metadata = None
            self._source_metadata = None

    def extract_internal_statistics(self) -> InternalStats:
        if self._mcap_path is None:
            return InternalStats(compression_format="unknown")

        try:
            return InternalStats(compression_format=detect_compression_format(self._mcap_path))
        except Exception:
            return InternalStats(compression_format="unknown")
