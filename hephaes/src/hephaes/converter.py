import logging
import os
from multiprocessing import Pool
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from ._converter_helpers import (
    JsonPayloadSerializer,
    _encode_raw_payload,
    _interpolate_json_leaves,
    _json_default as _json_default_impl,
    _normalize_payload,
    _SparseChunkBuilder,
    _step_ns_from_frequency,
    _TopicSamples,
)
from ._utils import determine_ros_version_from_path
from .conversion import build_message_decoder, discover_input_paths
from .conversion.assembly import (
    TopicPlan as _AssemblyTopicPlan,
    build_mapping_resolution as _build_mapping_resolution_stage,
    resolve_mapping_for_bag as _resolve_mapping_for_bag_stage,
)
from .manifest import build_episode_manifest, write_episode_manifest
from .models import (
    MappingTemplate,
    OutputConfig,
    ParquetOutputConfig,
    ResampleConfig,
    TFRecordOutputConfig,
)
from .outputs import DEFAULT_WRITER_REGISTRY, EpisodeContext, RecordBatch, WriterRegistry
from .profiler import extract_temporal_metadata
from .reader import RosReader

logger = logging.getLogger(__name__)
_OUTPUT_CONFIG_ADAPTER = TypeAdapter(OutputConfig)


TopicPlan = _AssemblyTopicPlan


def _default_episode_id(index: int) -> str:
    return f"episode_{index + 1:04d}"


def _json_default(obj: Any) -> Any:
    return _json_default_impl(obj)


def _resolve_mapping_for_bag(
    *,
    mapping: MappingTemplate,
    available_topics: dict[str, str],
) -> TopicPlan:
    return _resolve_mapping_for_bag_stage(
        mapping=mapping,
        available_topics=available_topics,
    )


def _resolve_output_config(
    output: OutputConfig | str,
) -> ParquetOutputConfig | TFRecordOutputConfig:
    if isinstance(output, str):
        if output not in {"parquet", "tfrecord"}:
            raise ValueError("output must be 'parquet' or 'tfrecord'")
        return _OUTPUT_CONFIG_ADAPTER.validate_python({"format": output})

    if isinstance(output, (ParquetOutputConfig, TFRecordOutputConfig)):
        return output

    raise TypeError(
        "output must be a string format name or an output config instance"
    )


def _build_episode_context(
    *,
    episode_id: str,
    bag_path: str | Path,
    ros_version: str,
    field_names: list[str],
    resample: ResampleConfig | None,
    output: ParquetOutputConfig | TFRecordOutputConfig,
) -> EpisodeContext:
    return EpisodeContext(
        episode_id=episode_id,
        source_path=Path(bag_path),
        ros_version=ros_version,
        field_names=list(field_names),
        resample=resample,
        output=output,
    )


def _build_mapping_resolution(
    *,
    field_names: list[str],
    topic_to_field: dict[str, str],
) -> dict[str, str | None]:
    return _build_mapping_resolution_stage(
        field_names=field_names,
        topic_to_field=topic_to_field,
    )


def _flush_chunk(
    *,
    builder: _SparseChunkBuilder,
    writer: Any,
) -> None:
    if builder.row_count == 0:
        return

    batch = RecordBatch(
        timestamps=list(builder.timestamps),
        field_data=builder.pop_field_data(),
    )
    writer.write_batch(batch)


def _iter_output_messages(
    *,
    reader: RosReader,
    topics: list[str],
    use_normalized_payloads: bool,
):
    if use_normalized_payloads:
        decoder = build_message_decoder()
        for message in decoder.iter_messages(reader, topics=topics):
            yield message.topic, int(message.timestamp), _normalize_payload(message.data)
        return

    for topic, timestamp, _msgtype, rawdata in reader.iter_raw_messages(topics=topics):
        yield topic, int(timestamp), _encode_raw_payload(rawdata)


def _convert_no_resample(
    *,
    reader: RosReader,
    plan: TopicPlan,
    writer: Any,
    all_field_names: list[str],
    bag_path: str,
    chunk_rows: int,
    use_normalized_payloads: bool,
) -> int:
    builder = _SparseChunkBuilder(all_field_names)
    current_timestamp: int | None = None
    row_values: dict[str, Any | None] = {}
    previous_timestamp: int | None = None
    rows_written = 0

    for topic, ts, payload in _iter_output_messages(
        reader=reader,
        topics=plan.topics_to_read,
        use_normalized_payloads=use_normalized_payloads,
    ):
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
                _flush_chunk(builder=builder, writer=writer)
            row_values = {}
            current_timestamp = ts

        row_values[plan.topic_to_field[topic]] = payload

    if current_timestamp is not None:
        builder.add_row(current_timestamp, row_values)
        rows_written += 1

    _flush_chunk(builder=builder, writer=writer)
    return rows_written


def _convert_downsample(
    *,
    reader: RosReader,
    plan: TopicPlan,
    writer: Any,
    all_field_names: list[str],
    bag_path: str,
    chunk_rows: int,
    freq_hz: float,
    use_normalized_payloads: bool,
) -> int:
    step_ns = _step_ns_from_frequency(freq_hz)

    builder = _SparseChunkBuilder(all_field_names)
    previous_timestamp: int | None = None
    bucket_start: int | None = None
    bucket_end: int | None = None
    bucket_values: dict[str, Any | None] = {}
    rows_written = 0

    for topic, ts, payload in _iter_output_messages(
        reader=reader,
        topics=plan.topics_to_read,
        use_normalized_payloads=use_normalized_payloads,
    ):
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
                _flush_chunk(builder=builder, writer=writer)
            bucket_values = {}
            bucket_start += step_ns
            bucket_end += step_ns

        bucket_values[plan.topic_to_field[topic]] = payload

    if bucket_start is not None:
        builder.add_row(bucket_start, bucket_values)
        rows_written += 1

    _flush_chunk(builder=builder, writer=writer)
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
    chunk_rows: int,
    freq_hz: float,
    use_normalized_payloads: bool,
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
        row_values: dict[str, Any | None] = {}

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
                if use_normalized_payloads:
                    row_values[field_name] = payloads[idx]
                else:
                    row_values[field_name] = serializer.dumps(payloads[idx])
                continue

            upper_idx = idx + 1
            if upper_idx >= len(timestamps):
                continue

            lo_ts = timestamps[idx]
            hi_ts = timestamps[upper_idx]
            if hi_ts == lo_ts:
                if use_normalized_payloads:
                    row_values[field_name] = payloads[idx]
                else:
                    row_values[field_name] = serializer.dumps(payloads[idx])
                continue

            alpha = (target_ts - lo_ts) / (hi_ts - lo_ts)
            interpolated = _interpolate_json_leaves(payloads[idx], payloads[upper_idx], alpha)
            if use_normalized_payloads:
                row_values[field_name] = interpolated
            else:
                row_values[field_name] = serializer.dumps(interpolated)

        builder.add_row(target_ts, row_values)
        rows_written += 1
        if builder.row_count >= chunk_rows:
            _flush_chunk(builder=builder, writer=writer)

        target_ts += step_ns

    _flush_chunk(builder=builder, writer=writer)
    return rows_written


def _convert_single_source(
    bag_path: str | Path,
    output_dir: str | Path,
    episode_id: str,
    mapping_dict: dict[str, list[str]],
    output_dict: dict[str, Any],
    resample_dict: dict[str, Any] | None,
    chunk_rows: int,
    writer_registry: WriterRegistry | None,
    write_manifest: bool,
    robot_context: dict[str, Any] | None,
) -> str:
    mapping = MappingTemplate.model_validate(mapping_dict)
    output = _OUTPUT_CONFIG_ADAPTER.validate_python(output_dict)
    resample = ResampleConfig.model_validate(resample_dict) if resample_dict is not None else None

    normalized_bag_path = str(bag_path)
    ros_version = determine_ros_version_from_path(normalized_bag_path)

    with RosReader.open(normalized_bag_path, ros_version=ros_version) as reader:
        plan = _resolve_mapping_for_bag(mapping=mapping, available_topics=reader.topics)
        if not plan.topics_to_read:
            raise ValueError(f"No requested topics from mapping were found in bag: {normalized_bag_path}")

        all_field_names = list(mapping.root.keys())
        use_normalized_payloads = output.format == "tfrecord"
        reader_metadata = reader.metadata
        temporal_metadata = extract_temporal_metadata(reader)
        context = _build_episode_context(
            episode_id=episode_id,
            bag_path=normalized_bag_path,
            ros_version=ros_version,
            field_names=all_field_names,
            resample=resample,
            output=output,
        )
        resolved_registry = writer_registry or DEFAULT_WRITER_REGISTRY

        with resolved_registry.create_writer(
            output_dir=output_dir,
            context=context,
            config=output,
        ) as writer:
            if resample is None:
                rows_written = _convert_no_resample(
                    reader=reader,
                    plan=plan,
                    writer=writer,
                    all_field_names=all_field_names,
                    bag_path=normalized_bag_path,
                    chunk_rows=chunk_rows,
                    use_normalized_payloads=use_normalized_payloads,
                )
            elif resample.method == "downsample":
                rows_written = _convert_downsample(
                    reader=reader,
                    plan=plan,
                    writer=writer,
                    all_field_names=all_field_names,
                    bag_path=normalized_bag_path,
                    chunk_rows=chunk_rows,
                    freq_hz=resample.freq_hz,
                    use_normalized_payloads=use_normalized_payloads,
                )
            else:
                rows_written = _convert_interpolate(
                    reader=reader,
                    plan=plan,
                    writer=writer,
                    all_field_names=all_field_names,
                    chunk_rows=chunk_rows,
                    freq_hz=resample.freq_hz,
                    use_normalized_payloads=use_normalized_payloads,
                )

        dataset_path = writer.path
        if write_manifest:
            manifest = build_episode_manifest(
                episode_id=episode_id,
                dataset_path=dataset_path,
                field_names=all_field_names,
                rows_written=rows_written,
                reader_metadata=reader_metadata,
                temporal_metadata=temporal_metadata,
                output=output,
                resample=resample,
                mapping_requested=mapping.root,
                mapping_resolved=_build_mapping_resolution(
                    field_names=all_field_names,
                    topic_to_field=plan.topic_to_field,
                ),
                robot_context=robot_context,
            )
            write_episode_manifest(manifest, dataset_path=dataset_path)

        logger.info("Finished %s: wrote %s rows to %s", episode_id, rows_written, writer.path)
        return str(writer.path)


class Converter:
    def __init__(
        self,
        file_paths: list[str | Path],
        mapping: MappingTemplate,
        output_dir: str | Path,
        *,
        output: OutputConfig | str = "parquet",
        resample: ResampleConfig | None = None,
        max_workers: int | None = None,
        chunk_rows: int = 50_000,
        writer_registry: WriterRegistry | None = None,
        write_manifest: bool = True,
        robot_context: dict[str, Any] | None = None,
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
        if writer_registry is not None and not isinstance(writer_registry, WriterRegistry):
            raise TypeError("writer_registry must be a WriterRegistry instance or None")
        if not isinstance(write_manifest, bool):
            raise TypeError("write_manifest must be a bool")
        if robot_context is not None and not isinstance(robot_context, dict):
            raise TypeError("robot_context must be a dict or None")

        discovered_file_paths = discover_input_paths(file_paths)
        for file_path in discovered_file_paths:
            determine_ros_version_from_path(file_path)

        self.file_paths = discovered_file_paths
        self.mapping = mapping
        self.output_dir = Path(output_dir)
        self.output = _resolve_output_config(output)
        self.resample = resample
        self.max_workers = max_workers
        self.chunk_rows = chunk_rows
        self.writer_registry = writer_registry or DEFAULT_WRITER_REGISTRY
        self.write_manifest = write_manifest
        self.robot_context = dict(robot_context) if robot_context is not None else None

    def convert(self) -> list[Path]:
        if not self.mapping.root:
            raise ValueError("No topics found in mapping template")

        mapping_dict = self.mapping.model_dump()
        output_dict = self.output.model_dump()
        resample_dict = self.resample.model_dump() if self.resample is not None else None

        requested_workers = self.max_workers or os.cpu_count() or 1
        workers = min(requested_workers, len(self.file_paths))
        logger.info(
            "Converting %d bag(s) with %d worker(s) to %s",
            len(self.file_paths),
            workers,
            self.output.format,
        )

        if workers <= 1:
            results = [
                _convert_single_source(
                    bag_path=str(bag_path),
                    output_dir=str(self.output_dir),
                    episode_id=_default_episode_id(index),
                    mapping_dict=mapping_dict,
                    output_dict=output_dict,
                    resample_dict=resample_dict,
                    chunk_rows=self.chunk_rows,
                    writer_registry=self.writer_registry,
                    write_manifest=self.write_manifest,
                    robot_context=self.robot_context,
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
                    output_dict,
                    resample_dict,
                    self.chunk_rows,
                    self.writer_registry,
                    self.write_manifest,
                    self.robot_context,
                )
                for index, bag_path in enumerate(self.file_paths)
            ]
            with Pool(processes=workers) as pool:
                results = pool.starmap(_convert_single_source, args)

        return [Path(path) for path in results]
