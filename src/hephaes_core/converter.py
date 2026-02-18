import base64
import json
import logging
import os
from dataclasses import asdict, dataclass, field, is_dataclass
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Callable, ContextManager, Protocol

from ._utils import determine_ros_version_from_path
from .models import MappingTemplate, RosVersion
from .reader import RosReader

logger = logging.getLogger(__name__)

_SUPPORTED_FORMATS = {"parquet"}


class TopicPlanner(Protocol):
    def plan(
        self,
        *,
        mapping: MappingTemplate,
        available_topics: dict[str, str],
        requested_topics: set[str],
    ) -> "TopicPlan": ...


class PayloadSerializer(Protocol):
    def dumps(self, payload: Any) -> str: ...


class RowSink(Protocol):
    path: Path

    def write_batch(
        self,
        *,
        bag_path: str,
        ros_version: RosVersion,
        message_indices: list[int],
        timestamps: list[int],
        topic_names: list[str],
        mapped_fields: list[str],
        topic_types: list[str],
        payload_json: list[str],
    ) -> None: ...


@dataclass(frozen=True)
class TopicPlan:
    topics_to_read: list[str]
    topic_rename_map: dict[str, str]


class DefaultTopicPlanner:
    def plan(
        self,
        *,
        mapping: MappingTemplate,
        available_topics: dict[str, str],
        requested_topics: set[str],
    ) -> TopicPlan:
        topics_to_read, topic_rename_map = _resolve_mapping_for_bag(
            mapping=mapping,
            available_topics=available_topics,
            requested_topics=requested_topics,
        )
        return TopicPlan(topics_to_read=topics_to_read, topic_rename_map=topic_rename_map)


class JsonPayloadSerializer:
    def dumps(self, payload: Any) -> str:
        return json.dumps(payload, default=_json_default)


class ParquetRowSink:
    def __init__(self, *, output_dir: str | Path, episode_id: str) -> None:
        from .parquet import ParquetWriter

        self._writer = ParquetWriter(output_dir=output_dir, episode_id=episode_id)
        self.path = self._writer.path

    def write_batch(
        self,
        *,
        bag_path: str,
        ros_version: RosVersion,
        message_indices: list[int],
        timestamps: list[int],
        topic_names: list[str],
        mapped_fields: list[str],
        topic_types: list[str],
        payload_json: list[str],
    ) -> None:
        self._writer.write_batch(
            bag_path=bag_path,
            ros_version=ros_version,
            message_indices=message_indices,
            timestamps=timestamps,
            topic_names=topic_names,
            mapped_fields=mapped_fields,
            topic_types=topic_types,
            payload_json=payload_json,
        )

    def close(self) -> None:
        self._writer.close()

    def __enter__(self) -> "ParquetRowSink":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def _default_episode_id(index: int) -> str:
    return f"episode_{index + 1:04d}"


def _default_row_sink_factory(output_dir: str | Path, episode_id: str) -> ContextManager[RowSink]:
    return ParquetRowSink(output_dir=output_dir, episode_id=episode_id)


def _json_default(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, (bytes, bytearray)):
        return {
            "__bytes__": True,
            "encoding": "base64",
            "value": base64.b64encode(obj).decode("ascii"),
        }
    if isinstance(obj, set):
        return list(obj)
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def _resolve_mapping_for_bag(
    *,
    mapping: MappingTemplate,
    available_topics: dict[str, str],
    requested_topics: set[str],
) -> tuple[list[str], dict[str, str]]:
    topics_to_read: list[str] = []
    topic_rename_map: dict[str, str] = {}

    for target_field, source_topics in mapping.root.items():
        for source_topic in source_topics:
            if source_topic in available_topics and source_topic in requested_topics:
                topics_to_read.append(source_topic)
                topic_rename_map[source_topic] = target_field
                break

    return topics_to_read, topic_rename_map


@dataclass
class _BatchBuffer:
    message_indices: list[int] = field(default_factory=list)
    timestamps: list[int] = field(default_factory=list)
    topic_names: list[str] = field(default_factory=list)
    mapped_fields: list[str] = field(default_factory=list)
    topic_types: list[str] = field(default_factory=list)
    payload_json: list[str] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.message_indices)

    def append(
        self,
        *,
        message_index: int,
        timestamp: int,
        topic_name: str,
        mapped_field: str,
        topic_type: str,
        payload_json: str,
    ) -> None:
        self.message_indices.append(message_index)
        self.timestamps.append(timestamp)
        self.topic_names.append(topic_name)
        self.mapped_fields.append(mapped_field)
        self.topic_types.append(topic_type)
        self.payload_json.append(payload_json)

    def clear(self) -> None:
        self.message_indices.clear()
        self.timestamps.clear()
        self.topic_names.clear()
        self.mapped_fields.clear()
        self.topic_types.clear()
        self.payload_json.clear()


def _flush_batch(
    *,
    sink: RowSink,
    batch: _BatchBuffer,
    bag_path: str,
    ros_version: RosVersion,
) -> int:
    if batch.size == 0:
        return 0

    row_count = batch.size
    sink.write_batch(
        bag_path=bag_path,
        ros_version=ros_version,
        message_indices=batch.message_indices,
        timestamps=batch.timestamps,
        topic_names=batch.topic_names,
        mapped_fields=batch.mapped_fields,
        topic_types=batch.topic_types,
        payload_json=batch.payload_json,
    )
    batch.clear()
    return row_count


def _convert_single(
    bag_path: str | Path,
    output_dir: str | Path,
    episode_id: str,
    topics: list[str],
    mapping_dict: dict[str, list[str]],
    batch_size: int,
    progress_every: int,
    topic_planner: TopicPlanner | None = None,
    payload_serializer: PayloadSerializer | None = None,
    row_sink_factory: Callable[[str | Path, str], ContextManager[RowSink]] | None = None,
) -> str:
    mapping = MappingTemplate.model_validate(mapping_dict)
    resolved_ros_version = determine_ros_version_from_path(bag_path)
    normalized_bag_path = str(bag_path)
    selected_topics = set(topics)

    resolved_topic_planner = topic_planner or DefaultTopicPlanner()
    resolved_payload_serializer = payload_serializer or JsonPayloadSerializer()
    resolved_row_sink_factory = row_sink_factory or _default_row_sink_factory

    written_rows = 0

    with RosReader.open(normalized_bag_path, ros_version=resolved_ros_version) as reader:
        known_topics = reader.topics
        plan = resolved_topic_planner.plan(
            mapping=mapping,
            available_topics=known_topics,
            requested_topics=selected_topics,
        )
        if not plan.topics_to_read:
            raise ValueError(f"No requested topics from mapping were found in bag: {normalized_bag_path}")

        logger.info(
            "Writing %s from %s (%s topics)",
            episode_id,
            Path(normalized_bag_path).name,
            len(plan.topics_to_read),
        )

        with resolved_row_sink_factory(output_dir, episode_id) as sink:
            batch = _BatchBuffer()

            for index, message in enumerate(reader.read_messages(topics=plan.topics_to_read)):
                batch.append(
                    message_index=index,
                    timestamp=int(message.timestamp),
                    topic_name=message.topic,
                    mapped_field=plan.topic_rename_map.get(message.topic, message.topic),
                    topic_type=known_topics.get(message.topic, "unknown"),
                    payload_json=resolved_payload_serializer.dumps(message.data),
                )
                if batch.size >= batch_size:
                    written_rows += _flush_batch(
                        sink=sink,
                        batch=batch,
                        bag_path=normalized_bag_path,
                        ros_version=resolved_ros_version,
                    )
                    if progress_every > 0 and written_rows % progress_every == 0:
                        logger.info("%s: wrote %s rows", episode_id, written_rows)

            written_rows += _flush_batch(
                sink=sink,
                batch=batch,
                bag_path=normalized_bag_path,
                ros_version=resolved_ros_version,
            )
            logger.info("Finished %s: wrote %s rows to %s", episode_id, written_rows, sink.path)
            return str(sink.path)


class Converter:
    def __init__(
        self,
        file_paths: list[str | Path],
        mapping: MappingTemplate,
        output_dir: str | Path,
        output_format: str = "parquet",
        *,
        batch_size: int = 5000,
        progress_every: int = 50000,
        max_workers: int | None = None,
        topic_planner: TopicPlanner | None = None,
        payload_serializer: PayloadSerializer | None = None,
        row_sink_factory: Callable[[str | Path, str], ContextManager[RowSink]] | None = None,
    ) -> None:
        if not isinstance(file_paths, list):
            raise TypeError("file_paths must be a list of file paths")
        if not file_paths:
            raise ValueError("file_paths must be non-empty")
        if output_format not in _SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported output format '{output_format}'. "
                f"Supported formats: {sorted(_SUPPORTED_FORMATS)}"
            )
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0")
        if progress_every < 0:
            raise ValueError("progress_every must be >= 0")
        if max_workers is not None and max_workers < 1:
            raise ValueError("max_workers must be >= 1 or None")

        for path in file_paths:
            determine_ros_version_from_path(path)

        self.file_paths = file_paths
        self.mapping = mapping
        self.output_dir = Path(output_dir)
        self.output_format = output_format
        self.batch_size = batch_size
        self.progress_every = progress_every
        self.max_workers = max_workers
        self.topic_planner = topic_planner
        self.payload_serializer = payload_serializer
        self.row_sink_factory = row_sink_factory

    def _derive_topics(self) -> list[str]:
        topics: list[str] = []
        for source_topics in self.mapping.root.values():
            for topic in source_topics:
                if topic not in topics:
                    topics.append(topic)
        return topics

    def convert(self) -> list[Path]:
        topics = self._derive_topics()
        if not topics:
            raise ValueError("No topics found in mapping template")

        mapping_dict = self.mapping.model_dump()
        workers = self.max_workers or os.cpu_count() or 1
        logger.info(
            "Converting %d file(s) with %d worker(s)",
            len(self.file_paths),
            workers,
        )

        has_custom_dependencies = any(
            dep is not None
            for dep in (self.topic_planner, self.payload_serializer, self.row_sink_factory)
        )
        if workers > 1 and has_custom_dependencies:
            raise ValueError("Custom conversion dependencies require max_workers=1")

        if workers == 1:
            results = [
                _convert_single(
                    str(bag_path),
                    str(self.output_dir),
                    _default_episode_id(index),
                    topics,
                    mapping_dict,
                    self.batch_size,
                    self.progress_every,
                    self.topic_planner,
                    self.payload_serializer,
                    self.row_sink_factory,
                )
                for index, bag_path in enumerate(self.file_paths)
            ]
        else:
            args = [
                (
                    str(bag_path),
                    str(self.output_dir),
                    _default_episode_id(index),
                    topics,
                    mapping_dict,
                    self.batch_size,
                    self.progress_every,
                )
                for index, bag_path in enumerate(self.file_paths)
            ]
            with Pool(processes=workers) as pool:
                results = pool.starmap(_convert_single, args)

        return [Path(r) for r in results]
