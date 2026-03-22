import logging
import os
from dataclasses import asdict
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
    construct_rows,
    build_mapping_resolution as _build_mapping_resolution_stage,
    resolve_mapping_for_bag as _resolve_mapping_for_bag_stage,
)
from .conversion.layout import (
    OutputRecord,
    partition_records_for_shards,
    partition_records_for_split,
    render_output_filename,
)
from .conversion.features import (
    FeatureBuilder,
    FeatureEvaluationContext,
    source_input_topics,
)
from .conversion.validation import validate_constructed_rows
from .conversion.report import write_conversion_report
from .manifest import build_episode_manifest, write_episode_manifest
from .models import (
    ConversionSpec,
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
    output_filename: str | None = None,
    split_name: str | None = None,
    shard_index: int | None = None,
    num_shards: int = 1,
) -> EpisodeContext:
    return EpisodeContext(
        episode_id=episode_id,
        source_path=Path(bag_path),
        ros_version=ros_version,
        field_names=list(field_names),
        resample=resample,
        output=output,
        output_filename=output_filename,
        split_name=split_name,
        shard_index=shard_index,
        num_shards=num_shards,
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


def _write_output_records(
    *,
    writer: Any,
    records: list[OutputRecord],
    field_names: list[str],
    chunk_rows: int,
) -> int:
    timestamps: list[int] = []
    field_data: dict[str, list[Any | None]] = {field_name: [] for field_name in field_names}
    presence_data: dict[str, list[int]] = {field_name: [] for field_name in field_names}
    rows_written = 0

    def _flush() -> None:
        nonlocal rows_written
        if not timestamps:
            return
        writer.write_batch(
            RecordBatch(
                timestamps=list(timestamps),
                field_data={name: list(values) for name, values in field_data.items()},
                presence_data={name: list(values) for name, values in presence_data.items()},
            )
        )
        rows_written += len(timestamps)
        timestamps.clear()
        for values in field_data.values():
            values.clear()
        for values in presence_data.values():
            values.clear()

    for record in records:
        timestamps.append(record.timestamp_ns)
        for field_name in field_names:
            field_data[field_name].append(record.field_data.get(field_name))
            presence_data[field_name].append(record.presence_data.get(field_name, 0))
        if len(timestamps) >= chunk_rows:
            _flush()

    _flush()
    return rows_written


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


def _build_schema_output_records(
    *,
    spec: ConversionSpec,
    records: list[Any],
) -> list[OutputRecord]:
    feature_builder = FeatureBuilder()
    field_names = list(spec.features.keys())
    output_records: list[OutputRecord] = []

    for record in records:
        row_values: dict[str, Any | None] = {}
        row_presence: dict[str, int] = {}
        context = FeatureEvaluationContext.from_row(
            timestamp_ns=int(record.timestamp_ns),
            values=record.values,
            presence=record.presence,
        )

        for feature_name, feature in spec.features.items():
            try:
                extracted_value = feature_builder.build(context, feature)
            except Exception:
                row_values[feature_name] = None
                row_presence[feature_name] = 0
                continue

            if extracted_value is None:
                row_values[feature_name] = None
                row_presence[feature_name] = 0
                continue

            row_values[feature_name] = extracted_value
            row_presence[feature_name] = 1

        output_records.append(
            OutputRecord(
                timestamp_ns=int(record.timestamp_ns),
                field_data={name: row_values.get(name) for name in field_names},
                presence_data={name: row_presence.get(name, 0) for name in field_names},
            )
        )

    return output_records


def _convert_schema_aware_source(
    *,
    reader: RosReader,
    spec: ConversionSpec,
    output_dir: str | Path,
    episode_id: str,
    writer_registry: WriterRegistry,
    ros_version: str,
    reader_metadata: Any,
    temporal_metadata: Any,
    write_manifest: bool,
    robot_context: dict[str, Any] | None,
    chunk_rows: int,
) -> tuple[list[Path], int, int]:
    if spec.row_strategy is None:
        raise ValueError("schema-aware conversion requires row_strategy")
    if not spec.features:
        raise ValueError("schema-aware conversion requires feature specs")

    row_result = construct_rows(
        reader=reader,
        spec=spec,
    )
    validation_summary = validate_constructed_rows(spec=spec, records=row_result.records)

    field_names = list(spec.features.keys())
    output_config = spec.to_output_config()
    output_records = _build_schema_output_records(spec=spec, records=row_result.records)
    split_partitions = partition_records_for_split(output_records, spec.split)
    split_counts = {split_name: len(split_records) for split_name, split_records in split_partitions.items()}
    output_paths: list[Path] = []
    total_rows_written = 0

    for split_name in sorted(split_partitions, key=lambda value: (value != "train", value != "val", value != "test", value)):
        split_records = split_partitions[split_name]
        shard_partitions = partition_records_for_shards(split_records, spec.output.shards)
        num_shards = spec.output.shards
        if not shard_partitions:
            continue

        for shard_index, shard_records in enumerate(shard_partitions):
            output_filename = render_output_filename(
                episode_id=episode_id,
                split_name=split_name,
                shard_index=shard_index,
                num_shards=num_shards,
                extension=spec.output.format,
                filename_template=spec.output.filename_template,
            )
            context = _build_episode_context(
                episode_id=episode_id,
                bag_path=str(reader.bag_path),
                ros_version=ros_version,
                field_names=field_names,
                resample=spec.resample,
                output=output_config,
                output_filename=output_filename,
                split_name=split_name,
                shard_index=shard_index,
                num_shards=num_shards,
            )

            with writer_registry.create_writer(
                output_dir=output_dir,
                context=context,
                config=output_config,
            ) as shard_writer:
                rows_written = _write_output_records(
                    writer=shard_writer,
                    records=shard_records,
                    field_names=field_names,
                    chunk_rows=chunk_rows,
                )

            total_rows_written += rows_written
            output_paths.append(shard_writer.path)

            if write_manifest and spec.output.write_manifest:
                if spec.mapping is not None:
                    mapping_requested = spec.mapping.root
                    mapping_resolved = _build_mapping_resolution(
                        field_names=field_names,
                        topic_to_field={
                            feature_name: (
                                source_topics[0] if len(source_topics) == 1 else None
                            )
                            for feature_name, feature in spec.features.items()
                            for source_topics in [source_input_topics(feature.source)]
                        },
                    )
                else:
                    mapping_requested = {
                        feature_name: source_input_topics(feature.source)
                        for feature_name, feature in spec.features.items()
                    }
                    mapping_resolved = {
                        feature_name: (
                            source_topics[0] if len(source_topics) == 1 else None
                        )
                        for feature_name, feature in spec.features.items()
                        for source_topics in [source_input_topics(feature.source)]
                    }

                manifest = build_episode_manifest(
                    episode_id=episode_id,
                    dataset_path=shard_writer.path,
                    field_names=field_names,
                    rows_written=rows_written,
                    reader_metadata=reader_metadata,
                    temporal_metadata=temporal_metadata,
                    output=output_config,
                    resample=spec.resample,
                    mapping_requested=mapping_requested,
                    mapping_resolved=mapping_resolved,
                    robot_context=robot_context,
                    schema=spec.schema.model_dump(),
                    features={name: feature.model_dump() for name, feature in spec.features.items()},
                    validation_summary=asdict(validation_summary),
                    split=spec.split.model_dump() if spec.split is not None else None,
                    split_name=split_name,
                    shard_index=shard_index,
                    num_shards=num_shards,
                    output_filename=output_filename,
                    dropped_rows=row_result.dropped_count,
                    split_counts=split_counts,
                    missing_feature_counts=validation_summary.missing_feature_counts,
                    missing_topic_counts=validation_summary.missing_topic_counts,
                    missing_feature_rates={
                        name: (
                            count / validation_summary.checked_records
                            if validation_summary.checked_records > 0
                            else 0.0
                        )
                        for name, count in validation_summary.missing_feature_counts.items()
                    },
                )
                write_episode_manifest(manifest, dataset_path=shard_writer.path)
                preview_rows = (
                    [asdict(record) for record in shard_records[: min(5, len(shard_records))]]
                    if spec.validation.preview
                    else None
                )
                write_conversion_report(
                    manifest=manifest,
                    dataset_path=shard_writer.path,
                    preview_rows=preview_rows,
                )

    logger.info(
        "Validated %s constructed row(s) for %s: %s bad, %s feature misses, %s missing source topic hits",
        validation_summary.checked_records,
        spec.schema.name,
        validation_summary.bad_records,
        sum(validation_summary.missing_feature_counts.values()),
        sum(validation_summary.missing_topic_counts.values()),
    )
    return output_paths, total_rows_written, row_result.dropped_count


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
    spec: ConversionSpec | None = None,
) -> list[str]:
    mapping = MappingTemplate.model_validate(mapping_dict)
    output = _OUTPUT_CONFIG_ADAPTER.validate_python(output_dict)
    resample = ResampleConfig.model_validate(resample_dict) if resample_dict is not None else None
    conversion_spec = (
        spec
        if spec is not None
        else ConversionSpec.from_legacy(
            mapping=mapping,
            output=output,
            resample=resample,
            write_manifest=write_manifest,
        )
    )

    normalized_bag_path = str(bag_path)
    ros_version = determine_ros_version_from_path(normalized_bag_path)

    with RosReader.open(normalized_bag_path, ros_version=ros_version) as reader:
        reader_metadata = reader.metadata
        temporal_metadata = extract_temporal_metadata(reader)
        resolved_registry = writer_registry or DEFAULT_WRITER_REGISTRY

        if conversion_spec.row_strategy is not None and conversion_spec.features:
            output_paths, rows_written, dropped_count = _convert_schema_aware_source(
                reader=reader,
                spec=conversion_spec,
                output_dir=output_dir,
                episode_id=episode_id,
                writer_registry=resolved_registry,
                ros_version=ros_version,
                reader_metadata=reader_metadata,
                temporal_metadata=temporal_metadata,
                write_manifest=write_manifest,
                robot_context=robot_context,
                chunk_rows=chunk_rows,
            )

            if dropped_count:
                logger.info(
                    "Row construction dropped %s record(s) for %s",
                    dropped_count,
                    episode_id,
                )
            logger.info(
                "Finished %s: wrote %s rows to %s",
                episode_id,
                rows_written,
                output_paths[-1] if output_paths else output_dir,
            )
            return [str(path) for path in output_paths]

        plan = _resolve_mapping_for_bag(mapping=mapping, available_topics=reader.topics)
        if not plan.topics_to_read:
            raise ValueError(
                f"No requested topics from mapping were found in bag: {normalized_bag_path}"
            )

        all_field_names = list(mapping.root.keys())
        use_normalized_payloads = output.format == "tfrecord"
        context = _build_episode_context(
            episode_id=episode_id,
            bag_path=normalized_bag_path,
            ros_version=ros_version,
            field_names=all_field_names,
            resample=resample,
            output=output,
        )

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
            write_conversion_report(manifest=manifest, dataset_path=dataset_path)

        logger.info("Finished %s: wrote %s rows to %s", episode_id, rows_written, writer.path)
        return [str(writer.path)]


class Converter:
    def __init__(
        self,
        file_paths: list[str | Path],
        mapping: MappingTemplate | None,
        output_dir: str | Path,
        *,
        spec: ConversionSpec | None = None,
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
        self.output_dir = Path(output_dir)
        if spec is None:
            if mapping is None:
                raise TypeError("mapping must be provided when spec is not set")
            resolved_output = _resolve_output_config(output)
            self.spec = ConversionSpec.from_legacy(
                mapping=mapping,
                output=resolved_output,
                resample=resample,
                write_manifest=write_manifest,
            )
            self.mapping = mapping
            self.output = resolved_output
            self.resample = resample
            self.write_manifest = write_manifest
        else:
            self.spec = spec
            self.mapping = mapping or spec.mapping or MappingTemplate.model_validate({})
            self.output = spec.to_output_config()
            self.resample = spec.resample
            self.write_manifest = write_manifest and spec.write_manifest
        self.max_workers = max_workers
        self.chunk_rows = chunk_rows
        self.writer_registry = writer_registry or DEFAULT_WRITER_REGISTRY
        self.robot_context = dict(robot_context) if robot_context is not None else None

    def convert(self) -> list[Path]:
        if self.spec.row_strategy is None and not self.mapping.root:
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
                    spec=self.spec,
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
                    self.spec,
                )
                for index, bag_path in enumerate(self.file_paths)
            ]
            with Pool(processes=workers) as pool:
                results = pool.starmap(_convert_single_source, args)

        flattened_results = [path for group in results for path in group]
        return [Path(path) for path in flattened_results]
