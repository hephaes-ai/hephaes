import base64
import json
import logging
import os
from dataclasses import asdict, dataclass, field, is_dataclass
from multiprocessing import Pool
from pathlib import Path
from typing import Any

try:
    import orjson as _orjson

    _ORJSON_AVAILABLE = True
except ImportError:  # pragma: no cover
    _orjson = None  # type: ignore[assignment]
    _ORJSON_AVAILABLE = False

from ._utils import determine_ros_version_from_path
from .models import MappingTemplate, ResampleConfig, RosVersion
from .reader import RosReader

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TopicPlan:
    topics_to_read: list[str]
    topic_to_field: dict[str, str]


@dataclass
class _TopicSamples:
    timestamps: list[int] = field(default_factory=list)
    payloads: list[Any] = field(default_factory=list)

    def append(self, timestamp: int, payload: Any) -> None:
        self.timestamps.append(timestamp)
        self.payloads.append(payload)

    def sort(self) -> None:
        if len(self.timestamps) <= 1:
            return
        order = sorted(range(len(self.timestamps)), key=self.timestamps.__getitem__)
        self.timestamps = [self.timestamps[i] for i in order]
        self.payloads = [self.payloads[i] for i in order]


class JsonPayloadSerializer:
    def dumps(self, payload: Any) -> str:
        if _ORJSON_AVAILABLE:
            return _orjson.dumps(
                payload,
                default=_json_default_orjson,
                option=_orjson.OPT_SERIALIZE_NUMPY | _orjson.OPT_NON_STR_KEYS,
            ).decode()
        return json.dumps(payload, default=_json_default)


class _SparseChunkBuilder:
    """Builds column chunks sparsely to avoid O(fields * rows) append overhead."""

    def __init__(self, field_names: list[str]) -> None:
        self._field_names = field_names
        self._columns: dict[str, list[str | None]] = {name: [] for name in field_names}
        self.timestamps: list[int] = []
        self.row_count = 0

    def add_row(self, timestamp: int, values: dict[str, str | None]) -> None:
        self.timestamps.append(timestamp)
        self.row_count += 1

        target_len = self.row_count
        for field_name, value in values.items():
            if value is None:
                continue
            column = self._columns[field_name]
            missing = target_len - 1 - len(column)
            if missing > 0:
                column.extend([None] * missing)
            column.append(value)

    def pop_field_data(self) -> dict[str, list[str | None]]:
        if self.row_count == 0:
            return {name: [] for name in self._field_names}

        for field_name in self._field_names:
            column = self._columns[field_name]
            if len(column) < self.row_count:
                column.extend([None] * (self.row_count - len(column)))

        data = self._columns
        self._columns = {name: [] for name in self._field_names}
        self.timestamps = []
        self.row_count = 0
        return data


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


def _encode_raw_payload(raw_payload: bytes) -> str:
    encoded = base64.b64encode(raw_payload).decode("ascii")
    return '{"__bytes__":true,"encoding":"base64","value":"' + encoded + '"}'


def _normalize_payload(payload: Any) -> Any:
    if payload is None or isinstance(payload, (bool, int, float, str)):
        return payload
    if is_dataclass(payload):
        return _normalize_payload(asdict(payload))
    if isinstance(payload, (bytes, bytearray)):
        return {
            "__bytes__": True,
            "encoding": "base64",
            "value": base64.b64encode(payload).decode("ascii"),
        }
    if isinstance(payload, dict):
        return {str(k): _normalize_payload(v) for k, v in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_normalize_payload(v) for v in payload]
    if isinstance(payload, set):
        return [_normalize_payload(v) for v in payload]
    if hasattr(payload, "__dict__"):
        return _normalize_payload(payload.__dict__)
    return str(payload)


def _resolve_mapping_for_bag(
    *,
    mapping: MappingTemplate,
    available_topics: dict[str, str],
) -> TopicPlan:
    topics_to_read: list[str] = []
    topic_to_field: dict[str, str] = {}

    for target_field, source_topics in mapping.root.items():
        for source_topic in source_topics:
            if source_topic in available_topics:
                topics_to_read.append(source_topic)
                topic_to_field[source_topic] = target_field
                break

    return TopicPlan(topics_to_read=topics_to_read, topic_to_field=topic_to_field)


def _interpolate_json_leaves(lo: Any, hi: Any, alpha: float) -> Any:
    if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
        return lo + alpha * (hi - lo)
    if isinstance(lo, dict) and isinstance(hi, dict):
        return {k: _interpolate_json_leaves(lo[k], hi[k], alpha) for k in lo if k in hi}
    if isinstance(lo, list) and isinstance(hi, list) and len(lo) == len(hi):
        return [_interpolate_json_leaves(a, b, alpha) for a, b in zip(lo, hi)]
    return lo


def _step_ns_from_frequency(freq_hz: float) -> int:
    step_ns = int(round(1e9 / freq_hz))
    if step_ns <= 0:
        raise ValueError("resample frequency is too large to produce a finite grid")
    return step_ns


def _flush_chunk(
    *,
    builder: _SparseChunkBuilder,
    writer: Any,
    bag_path: str,
    ros_version: RosVersion,
) -> None:
    if builder.row_count == 0:
        return

    timestamps = builder.timestamps
    field_data = builder.pop_field_data()
    writer.write_table(
        bag_path=bag_path,
        ros_version=ros_version,
        timestamps=timestamps,
        field_data=field_data,
    )


def _convert_no_resample(
    *,
    reader: RosReader,
    plan: TopicPlan,
    writer: Any,
    all_field_names: list[str],
    bag_path: str,
    ros_version: RosVersion,
    chunk_rows: int,
) -> int:
    builder = _SparseChunkBuilder(all_field_names)
    current_timestamp: int | None = None
    row_values: dict[str, str | None] = {}
    previous_timestamp: int | None = None
    rows_written = 0

    for topic, timestamp, _msgtype, rawdata in reader.iter_raw_messages(topics=plan.topics_to_read):
        ts = int(timestamp)
        if previous_timestamp is not None and ts < previous_timestamp:
            raise ValueError(
                f"Bag messages are out of order for '{bag_path}'. "
                "Streaming conversion requires non-decreasing timestamps."
            )
        previous_timestamp = ts

        if current_timestamp is None:
            current_timestamp = ts
        elif ts != current_timestamp:
            builder.add_row(current_timestamp, row_values)
            rows_written += 1
            if builder.row_count >= chunk_rows:
                _flush_chunk(builder=builder, writer=writer, bag_path=bag_path, ros_version=ros_version)
            row_values = {}
            current_timestamp = ts

        row_values[plan.topic_to_field[topic]] = _encode_raw_payload(rawdata)

    if current_timestamp is not None:
        builder.add_row(current_timestamp, row_values)
        rows_written += 1

    _flush_chunk(builder=builder, writer=writer, bag_path=bag_path, ros_version=ros_version)
    return rows_written


def _convert_downsample(
    *,
    reader: RosReader,
    plan: TopicPlan,
    writer: Any,
    all_field_names: list[str],
    bag_path: str,
    ros_version: RosVersion,
    chunk_rows: int,
    freq_hz: float,
) -> int:
    step_ns = _step_ns_from_frequency(freq_hz)

    builder = _SparseChunkBuilder(all_field_names)
    previous_timestamp: int | None = None
    bucket_start: int | None = None
    bucket_end: int | None = None
    bucket_values: dict[str, str | None] = {}
    rows_written = 0

    for topic, timestamp, _msgtype, rawdata in reader.iter_raw_messages(topics=plan.topics_to_read):
        ts = int(timestamp)
        if previous_timestamp is not None and ts < previous_timestamp:
            raise ValueError(
                f"Bag messages are out of order for '{bag_path}'. "
                "Streaming conversion requires non-decreasing timestamps."
            )
        previous_timestamp = ts

        if bucket_start is None:
            bucket_start = ts
            bucket_end = bucket_start + step_ns

        while bucket_end is not None and ts >= bucket_end:
            builder.add_row(bucket_start, bucket_values)
            rows_written += 1
            if builder.row_count >= chunk_rows:
                _flush_chunk(builder=builder, writer=writer, bag_path=bag_path, ros_version=ros_version)
            bucket_values = {}
            bucket_start += step_ns
            bucket_end += step_ns

        bucket_values[plan.topic_to_field[topic]] = _encode_raw_payload(rawdata)

    if bucket_start is not None:
        builder.add_row(bucket_start, bucket_values)
        rows_written += 1

    _flush_chunk(builder=builder, writer=writer, bag_path=bag_path, ros_version=ros_version)
    return rows_written


def _collect_interpolation_samples(
    *,
    reader: RosReader,
    plan: TopicPlan,
    all_field_names: list[str],
) -> tuple[dict[str, _TopicSamples], int | None, int | None]:
    buffers = {field_name: _TopicSamples() for field_name in all_field_names}

    min_ts: int | None = None
    max_ts: int | None = None

    for message in reader.read_messages(topics=plan.topics_to_read):
        ts = int(message.timestamp)
        field_name = plan.topic_to_field[message.topic]
        buffers[field_name].append(ts, _normalize_payload(message.data))

        if min_ts is None or ts < min_ts:
            min_ts = ts
        if max_ts is None or ts > max_ts:
            max_ts = ts

    for sample in buffers.values():
        sample.sort()

    return buffers, min_ts, max_ts


def _convert_interpolate(
    *,
    reader: RosReader,
    plan: TopicPlan,
    writer: Any,
    all_field_names: list[str],
    bag_path: str,
    ros_version: RosVersion,
    chunk_rows: int,
    freq_hz: float,
) -> int:
    samples, min_ts, max_ts = _collect_interpolation_samples(
        reader=reader,
        plan=plan,
        all_field_names=all_field_names,
    )
    if min_ts is None or max_ts is None:
        return 0

    step_ns = _step_ns_from_frequency(freq_hz)
    builder = _SparseChunkBuilder(all_field_names)
    lower_indices = {field_name: 0 for field_name in all_field_names}
    serializer = JsonPayloadSerializer()
    rows_written = 0

    target_ts = min_ts
    while target_ts <= max_ts:
        row_values: dict[str, str | None] = {}

        for field_name in all_field_names:
            sample = samples[field_name]
            if not sample.timestamps:
                continue

            timestamps = sample.timestamps
            payloads = sample.payloads
            idx = lower_indices[field_name]
            if idx >= len(timestamps):
                idx = len(timestamps) - 1

            if target_ts < timestamps[0] or target_ts > timestamps[-1]:
                lower_indices[field_name] = idx
                continue

            while idx + 1 < len(timestamps) and timestamps[idx + 1] <= target_ts:
                idx += 1
            lower_indices[field_name] = idx

            if timestamps[idx] == target_ts:
                row_values[field_name] = serializer.dumps(payloads[idx])
                continue

            upper_idx = idx + 1
            if upper_idx >= len(timestamps):
                continue

            lo_ts = timestamps[idx]
            hi_ts = timestamps[upper_idx]
            if hi_ts == lo_ts:
                row_values[field_name] = serializer.dumps(payloads[idx])
                continue

            alpha = (target_ts - lo_ts) / (hi_ts - lo_ts)
            row_values[field_name] = serializer.dumps(
                _interpolate_json_leaves(payloads[idx], payloads[upper_idx], alpha)
            )

        builder.add_row(target_ts, row_values)
        rows_written += 1
        if builder.row_count >= chunk_rows:
            _flush_chunk(builder=builder, writer=writer, bag_path=bag_path, ros_version=ros_version)

        target_ts += step_ns

    _flush_chunk(builder=builder, writer=writer, bag_path=bag_path, ros_version=ros_version)
    return rows_written


def _convert_single_bag(
    bag_path: str | Path,
    output_dir: str | Path,
    episode_id: str,
    mapping_dict: dict[str, list[str]],
    resample_dict: dict[str, Any] | None,
    chunk_rows: int,
) -> str:
    mapping = MappingTemplate.model_validate(mapping_dict)
    resample = ResampleConfig.model_validate(resample_dict) if resample_dict is not None else None

    normalized_bag_path = str(bag_path)
    ros_version = determine_ros_version_from_path(normalized_bag_path)

    with RosReader.open(normalized_bag_path, ros_version=ros_version) as reader:
        plan = _resolve_mapping_for_bag(mapping=mapping, available_topics=reader.topics)
        if not plan.topics_to_read:
            raise ValueError(f"No requested topics from mapping were found in bag: {normalized_bag_path}")

        all_field_names = list(mapping.root.keys())

        from .parquet import WideParquetWriter

        with WideParquetWriter(
            output_dir=output_dir,
            episode_id=episode_id,
            field_names=all_field_names,
        ) as writer:
            if resample is None:
                rows_written = _convert_no_resample(
                    reader=reader,
                    plan=plan,
                    writer=writer,
                    all_field_names=all_field_names,
                    bag_path=normalized_bag_path,
                    ros_version=ros_version,
                    chunk_rows=chunk_rows,
                )
            elif resample.method == "downsample":
                rows_written = _convert_downsample(
                    reader=reader,
                    plan=plan,
                    writer=writer,
                    all_field_names=all_field_names,
                    bag_path=normalized_bag_path,
                    ros_version=ros_version,
                    chunk_rows=chunk_rows,
                    freq_hz=resample.freq_hz,
                )
            else:
                rows_written = _convert_interpolate(
                    reader=reader,
                    plan=plan,
                    writer=writer,
                    all_field_names=all_field_names,
                    bag_path=normalized_bag_path,
                    ros_version=ros_version,
                    chunk_rows=chunk_rows,
                    freq_hz=resample.freq_hz,
                )

        logger.info("Finished %s: wrote %s rows to %s", episode_id, rows_written, writer.path)
        return str(writer.path)


class Converter:
    def __init__(
        self,
        file_paths: list[str | Path],
        mapping: MappingTemplate,
        output_dir: str | Path,
        *,
        resample: ResampleConfig | None = None,
        max_workers: int | None = None,
        chunk_rows: int = 50_000,
    ) -> None:
        if not isinstance(file_paths, list):
            raise TypeError("file_paths must be a list of file paths")
        if not file_paths:
            raise ValueError("file_paths must be non-empty")
        if max_workers is not None and max_workers < 1:
            raise ValueError("max_workers must be >= 1 or None")
        if chunk_rows < 1:
            raise ValueError("chunk_rows must be >= 1")
        if resample is not None and not isinstance(resample, ResampleConfig):
            raise TypeError("resample must be a ResampleConfig instance or None")

        for file_path in file_paths:
            determine_ros_version_from_path(file_path)

        self.file_paths = [Path(path) for path in file_paths]
        self.mapping = mapping
        self.output_dir = Path(output_dir)
        self.resample = resample
        self.max_workers = max_workers
        self.chunk_rows = chunk_rows

    def convert(self) -> list[Path]:
        if not self.mapping.root:
            raise ValueError("No topics found in mapping template")

        mapping_dict = self.mapping.model_dump()
        resample_dict = self.resample.model_dump() if self.resample is not None else None

        requested_workers = self.max_workers or os.cpu_count() or 1
        workers = min(requested_workers, len(self.file_paths))
        logger.info("Converting %d bag(s) with %d worker(s)", len(self.file_paths), workers)

        if workers <= 1:
            results = [
                _convert_single_bag(
                    bag_path=str(bag_path),
                    output_dir=str(self.output_dir),
                    episode_id=_default_episode_id(index),
                    mapping_dict=mapping_dict,
                    resample_dict=resample_dict,
                    chunk_rows=self.chunk_rows,
                )
                for index, bag_path in enumerate(self.file_paths)
            ]
        else:
            args = [
                (
                    str(bag_path),
                    str(self.output_dir),
                    _default_episode_id(index),
                    mapping_dict,
                    resample_dict,
                    self.chunk_rows,
                )
                for index, bag_path in enumerate(self.file_paths)
            ]
            with Pool(processes=workers) as pool:
                results = pool.starmap(_convert_single_bag, args)

        return [Path(path) for path in results]
