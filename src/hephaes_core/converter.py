import base64
import bisect
import json
import logging
import os
from dataclasses import asdict, dataclass, field, is_dataclass
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Callable, ContextManager, Literal, Protocol

try:
    import orjson as _orjson
    _ORJSON_AVAILABLE = True
except ImportError:  # pragma: no cover
    _orjson = None  # type: ignore[assignment]
    _ORJSON_AVAILABLE = False

from ._utils import determine_ros_version_from_path
from .models import MappingTemplate, ResampleMethod, RosVersion
from .reader import RosReader

logger = logging.getLogger(__name__)


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
        if _ORJSON_AVAILABLE:
            return _orjson.dumps(
                payload,
                default=_json_default_orjson,
                option=_orjson.OPT_SERIALIZE_NUMPY | _orjson.OPT_NON_STR_KEYS,
            ).decode()
        return json.dumps(payload, default=_json_default)


def _default_episode_id(index: int) -> str:
    return f"episode_{index + 1:04d}"


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


def _json_default_orjson(obj: Any) -> Any:
    # orjson handles dataclasses and numpy natively; handle remaining types here
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
class _TopicBuffer:
    """Accumulates all (timestamp_ns, payload_json) for one mapped field."""
    timestamps: list[int] = field(default_factory=list)
    payloads: list[str] = field(default_factory=list)

    def append(self, timestamp: int, payload_json: str) -> None:
        self.timestamps.append(timestamp)
        self.payloads.append(payload_json)

    def __len__(self) -> int:
        return len(self.timestamps)

    def sort(self) -> None:
        if len(self.timestamps) > 1:
            paired = sorted(zip(self.timestamps, self.payloads))
            self.timestamps = [p[0] for p in paired]
            self.payloads = [p[1] for p in paired]


def _build_time_grid(
    *,
    topic_buffers: dict[str, _TopicBuffer],
    resample_freq_hz: float | None,
) -> list[int]:
    if resample_freq_hz is not None:
        all_ts = [ts for buf in topic_buffers.values() for ts in buf.timestamps]
        if not all_ts:
            return []
        t_start = min(all_ts)
        t_end = max(all_ts)
        step_ns = int(round(1e9 / resample_freq_hz))
        if step_ns <= 0:
            raise ValueError("resample_freq_hz is too large to produce a finite grid")
        grid: list[int] = []
        t = t_start
        while t <= t_end:
            grid.append(t)
            t += step_ns
        return grid
    else:
        all_ts_set: set[int] = set()
        for buf in topic_buffers.values():
            all_ts_set.update(buf.timestamps)
        return sorted(all_ts_set)


def _interpolate_json_leaves(lo: Any, hi: Any, alpha: float) -> Any:
    if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
        return lo + alpha * (hi - lo)
    if isinstance(lo, dict) and isinstance(hi, dict):
        return {k: _interpolate_json_leaves(lo[k], hi[k], alpha) for k in lo if k in hi}
    if isinstance(lo, list) and isinstance(hi, list) and len(lo) == len(hi):
        return [_interpolate_json_leaves(a, b, alpha) for a, b in zip(lo, hi)]
    return lo  # forward-fill fallback for non-numeric / shape mismatch


def _resample_field(
    *,
    buf: _TopicBuffer,
    grid: list[int],
    method: str,
    serializer: PayloadSerializer,
) -> list[str | None]:
    if not buf.timestamps:
        return [None] * len(grid)

    if method == "ffill":
        result: list[str | None] = []
        ptr = 0
        last: str | None = None
        for target_ts in grid:
            while ptr < len(buf.timestamps) and buf.timestamps[ptr] <= target_ts:
                last = buf.payloads[ptr]
                ptr += 1
            result.append(last)
        return result

    # interpolate
    result = []
    for target_ts in grid:
        lo_idx = bisect.bisect_right(buf.timestamps, target_ts) - 1
        hi_idx = lo_idx + 1

        if lo_idx < 0:
            result.append(None)
            continue

        lo_payload = buf.payloads[lo_idx]

        if hi_idx >= len(buf.timestamps):
            result.append(lo_payload)
            continue

        lo_ts = buf.timestamps[lo_idx]
        hi_ts = buf.timestamps[hi_idx]

        if lo_ts == hi_ts or target_ts == lo_ts:
            result.append(lo_payload)
            continue

        alpha = (target_ts - lo_ts) / (hi_ts - lo_ts)
        lo_obj = json.loads(lo_payload)
        hi_obj = json.loads(buf.payloads[hi_idx])
        interpolated = _interpolate_json_leaves(lo_obj, hi_obj, alpha)
        result.append(serializer.dumps(interpolated))

    return result


def _convert_single_wide(
    bag_path: str | Path,
    output_dir: str | Path,
    episode_id: str,
    topics: list[str],
    mapping_dict: dict[str, list[str]],
    resample_freq_hz: float | None,
    resample_method: str,
    topic_planner: TopicPlanner | None = None,
    payload_serializer: PayloadSerializer | None = None,
) -> str:
    mapping = MappingTemplate.model_validate(mapping_dict)
    resolved_ros_version = determine_ros_version_from_path(bag_path)
    normalized_bag_path = str(bag_path)
    selected_topics = set(topics)

    resolved_topic_planner = topic_planner or DefaultTopicPlanner()
    resolved_payload_serializer = payload_serializer or JsonPayloadSerializer()

    # Phase 1: collect all messages into per-field buffers
    with RosReader.open(normalized_bag_path, ros_version=resolved_ros_version) as reader:
        known_topics = reader.topics
        plan = resolved_topic_planner.plan(
            mapping=mapping,
            available_topics=known_topics,
            requested_topics=selected_topics,
        )
        if not plan.topics_to_read:
            raise ValueError(
                f"No requested topics from mapping were found in bag: {normalized_bag_path}"
            )

        logger.info(
            "Wide conversion: collecting messages from %s (%s topics)",
            Path(normalized_bag_path).name,
            len(plan.topics_to_read),
        )

        # All field names in mapping order (even ones absent from this bag)
        all_field_names: list[str] = list(mapping.root.keys())
        # Resolved fields (fields that have a matching topic in this bag)
        resolved_fields = set(plan.topic_rename_map.values())
        topic_buffers: dict[str, _TopicBuffer] = {
            fname: _TopicBuffer() for fname in all_field_names if fname in resolved_fields
        }

        for _index, (topic, timestamp, _msgtype, rawdata) in enumerate(
            reader.iter_raw_messages(topics=plan.topics_to_read)
        ):
            field_name = plan.topic_rename_map[topic]
            payload = resolved_payload_serializer.dumps(rawdata)
            topic_buffers[field_name].append(int(timestamp), payload)

    # Sort each buffer by timestamp (handles out-of-order bags)
    for buf in topic_buffers.values():
        buf.sort()

    # Phase 2: build time grid and resample
    grid = _build_time_grid(
        topic_buffers=topic_buffers,
        resample_freq_hz=resample_freq_hz,
    )

    field_data: dict[str, list[str | None]] = {}
    for fname in all_field_names:
        if fname in topic_buffers:
            field_data[fname] = _resample_field(
                buf=topic_buffers[fname],
                grid=grid,
                method=resample_method,
                serializer=resolved_payload_serializer,
            )
        else:
            field_data[fname] = [None] * len(grid)

    # Phase 3: write wide parquet
    from .parquet import WideParquetWriter

    with WideParquetWriter(
        output_dir=output_dir,
        episode_id=episode_id,
        field_names=all_field_names,
    ) as writer:
        writer.write_table(
            bag_path=normalized_bag_path,
            ros_version=resolved_ros_version,
            timestamps=grid,
            field_data=field_data,
        )
        logger.info(
            "Finished %s: wrote %s wide rows to %s",
            episode_id,
            len(grid),
            writer.path,
        )
        return str(writer.path)


class Converter:
    def __init__(
        self,
        file_paths: list[str | Path],
        mapping: MappingTemplate,
        output_dir: str | Path,
        *,
        progress_every: int = 50000,
        max_workers: int | None = None,
        resample_freq_hz: float | None = None,
        resample_method: ResampleMethod = "ffill",
        topic_planner: TopicPlanner | None = None,
        payload_serializer: PayloadSerializer | None = None,
    ) -> None:
        if not isinstance(file_paths, list):
            raise TypeError("file_paths must be a list of file paths")
        if not file_paths:
            raise ValueError("file_paths must be non-empty")
        if progress_every < 0:
            raise ValueError("progress_every must be >= 0")
        if max_workers is not None and max_workers < 1:
            raise ValueError("max_workers must be >= 1 or None")
        if resample_freq_hz is not None and resample_freq_hz <= 0:
            raise ValueError("resample_freq_hz must be positive")
        if resample_method not in ("ffill", "interpolate"):
            raise ValueError("resample_method must be 'ffill' or 'interpolate'")

        for path in file_paths:
            determine_ros_version_from_path(path)

        self.file_paths = file_paths
        self.mapping = mapping
        self.output_dir = Path(output_dir)
        self.progress_every = progress_every
        self.max_workers = max_workers
        self.resample_freq_hz = resample_freq_hz
        self.resample_method = resample_method
        self.topic_planner = topic_planner
        self.payload_serializer = payload_serializer

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
            dep is not None for dep in (self.topic_planner, self.payload_serializer)
        )
        if workers > 1 and has_custom_dependencies:
            raise ValueError("Custom conversion dependencies require max_workers=1")

        if workers == 1:
            results = [
                _convert_single_wide(
                    str(bag_path),
                    str(self.output_dir),
                    _default_episode_id(index),
                    topics,
                    mapping_dict,
                    self.resample_freq_hz,
                    self.resample_method,
                    self.topic_planner,
                    self.payload_serializer,
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
                    self.resample_freq_hz,
                    self.resample_method,
                )
                for index, bag_path in enumerate(self.file_paths)
            ]
            with Pool(processes=workers) as pool:
                results = pool.starmap(_convert_single_wide, args)

        return [Path(r) for r in results]
