import logging
import os
from dataclasses import dataclass
from multiprocessing import Pool
from pathlib import Path

from ._utils import (
    determine_ros_version_from_path,
    determine_storage_format_from_path,
    timestamp_to_iso,
)
from .models import BagMetadata, ReaderMetadata, TemporalMetadata, Topic
from .reader import RosReader

logger = logging.getLogger(__name__)


@dataclass
class _TopicStats:
    count: int = 0
    first_timestamp: int | None = None
    last_timestamp: int | None = None

    def update(self, timestamp: int) -> None:
        self.count += 1
        if self.first_timestamp is None or timestamp < self.first_timestamp:
            self.first_timestamp = timestamp
        if self.last_timestamp is None or timestamp > self.last_timestamp:
            self.last_timestamp = timestamp


@dataclass
class _MessageScan:
    start_timestamp: int | None
    end_timestamp: int | None
    message_count: int
    topic_stats: dict[str, _TopicStats]


def _scan_messages(reader: RosReader, *, progress_context: str) -> _MessageScan:
    start_timestamp: int | None = None
    end_timestamp: int | None = None
    message_count = 0
    topic_stats: dict[str, _TopicStats] = {}

    for topic, timestamp in reader.iter_message_headers():
        if start_timestamp is None or timestamp < start_timestamp:
            start_timestamp = timestamp
        if end_timestamp is None or timestamp > end_timestamp:
            end_timestamp = timestamp

        stats = topic_stats.setdefault(topic, _TopicStats())
        stats.update(timestamp)

        message_count += 1
        if message_count % 10000 == 0:
            logger.info("Processed %s messages while %s", message_count, progress_context)

    return _MessageScan(
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        message_count=message_count,
        topic_stats=topic_stats,
    )


def _build_temporal_metadata(
    *,
    start_timestamp: int | None,
    end_timestamp: int | None,
    message_count: int,
) -> TemporalMetadata:
    duration_seconds = (
        (end_timestamp - start_timestamp) / 1e9
        if start_timestamp is not None and end_timestamp is not None
        else 0
    )
    start_time_iso = timestamp_to_iso(start_timestamp) if start_timestamp is not None else None
    end_time_iso = timestamp_to_iso(end_timestamp) if end_timestamp is not None else None
    return TemporalMetadata(
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        start_time_iso=start_time_iso,
        end_time_iso=end_time_iso,
        duration_seconds=duration_seconds,
        message_count=message_count,
    )


def _build_topics(topic_types: dict[str, str], topic_stats: dict[str, _TopicStats]) -> list[Topic]:
    topics: list[Topic] = []
    for topic_name, msg_type in topic_types.items():
        stats = topic_stats.get(topic_name, _TopicStats())
        topic_duration = (
            (stats.last_timestamp - stats.first_timestamp) / 1e9
            if stats.first_timestamp is not None and stats.last_timestamp is not None
            else 0
        )
        rate_hz = stats.count / topic_duration if topic_duration > 0 else 0
        topics.append(
            Topic(
                name=topic_name,
                message_type=msg_type,
                message_count=stats.count,
                rate_hz=round(rate_hz, 2),
            )
        )

    topic_names = [topic.name for topic in topics]
    if len(topic_names) != len(set(topic_names)):
        raise ValueError("topic names must be unique")
    return topics


def extract_reader_metadata(
    reader_metadata: ReaderMetadata,
    *,
    metadata_file_path: str | None = None,
    metadata_path: str | None = None,
) -> ReaderMetadata:
    if metadata_file_path is not None and metadata_path is not None:
        if metadata_file_path != metadata_path:
            raise ValueError("metadata_file_path and metadata_path must match when both are provided")
    resolved_metadata_file_path = metadata_file_path or metadata_path

    if resolved_metadata_file_path is None:
        return reader_metadata

    path_value = resolved_metadata_file_path
    file_path_value = resolved_metadata_file_path
    return reader_metadata.model_copy(
        update={
            "path": path_value,
            "file_path": file_path_value,
            "storage_format": determine_storage_format_from_path(file_path_value),
        }
    )


def extract_temporal_metadata(reader: RosReader) -> TemporalMetadata:
    start_time = reader.start_time
    end_time = reader.end_time
    if start_time is None or end_time is None:
        scan = _scan_messages(reader, progress_context="computing temporal metadata")
        return _build_temporal_metadata(
            start_timestamp=scan.start_timestamp,
            end_timestamp=scan.end_timestamp,
            message_count=scan.message_count,
        )
    return _build_temporal_metadata(
        start_timestamp=start_time,
        end_timestamp=end_time,
        message_count=reader.message_count,
    )


def _collect_temporal_metadata_and_topics(reader: RosReader) -> tuple[TemporalMetadata, list[Topic]]:
    scan = _scan_messages(reader, progress_context="profiling")
    temporal_metadata = _build_temporal_metadata(
        start_timestamp=scan.start_timestamp,
        end_timestamp=scan.end_timestamp,
        message_count=scan.message_count,
    )
    topics = _build_topics(reader.topics, scan.topic_stats)
    return temporal_metadata, topics


def extract_topics(reader: RosReader) -> list[Topic]:
    scan = _scan_messages(reader, progress_context="extracting topics")
    return _build_topics(reader.topics, scan.topic_stats)


def _profile_single(
    bag_path: str,
    metadata_file_path: str | None = None,
    file_path: str | None = None,
) -> BagMetadata:
    if metadata_file_path is not None and file_path is not None:
        if metadata_file_path != file_path:
            raise ValueError("metadata_file_path and file_path must match when both are provided")
    resolved_metadata_file_path = metadata_file_path or file_path

    ros_version = determine_ros_version_from_path(bag_path)

    with RosReader.open(bag_path, ros_version=ros_version) as reader:
        reader_metadata = extract_reader_metadata(
            reader.metadata,
            metadata_file_path=resolved_metadata_file_path,
        )
        temporal_metadata, topics = _collect_temporal_metadata_and_topics(reader)
        internal_stats = reader.extract_internal_statistics()
        return BagMetadata(
            **reader_metadata.model_dump(exclude={"source_metadata"}),
            **temporal_metadata.model_dump(),
            topics=topics,
            **internal_stats.model_dump(),
        )


class Profiler:
    def __init__(
        self,
        bag_paths: list[str | Path],
        *,
        max_workers: int | None = None,
    ) -> None:
        if not isinstance(bag_paths, list):
            raise TypeError("bag_paths must be a list")
        if not bag_paths:
            raise ValueError("bag_paths must be non-empty")
        if max_workers is not None and max_workers < 1:
            raise ValueError("max_workers must be >= 1 or None")

        for path in bag_paths:
            determine_ros_version_from_path(path)

        self.bag_paths = bag_paths
        self.max_workers = max_workers

    def profile(self) -> list[BagMetadata]:
        args = [(str(p),) for p in self.bag_paths]
        workers = self.max_workers or os.cpu_count() or 1
        logger.info("Profiling %d bag(s) with %d worker(s)", len(self.bag_paths), workers)

        if workers == 1:
            return [_profile_single(*a) for a in args]

        with Pool(processes=workers) as pool:
            return pool.starmap(_profile_single, args)
