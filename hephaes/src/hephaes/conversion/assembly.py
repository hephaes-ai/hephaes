from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .._converter_helpers import (
    JsonPayloadSerializer,
    _encode_raw_payload,
    _interpolate_json_leaves,
    _normalize_payload,
    _SparseChunkBuilder,
    _step_ns_from_frequency,
    _TopicSamples,
)
from ..models import MappingTemplate
from ..outputs.base import RecordBatch
from ..reader import RosReader


@dataclass(frozen=True)
class TopicPlan:
    topics_to_read: list[str]
    topic_to_field: dict[str, str]


def resolve_mapping_for_bag(
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


def build_mapping_resolution(
    *,
    field_names: list[str],
    topic_to_field: dict[str, str],
) -> dict[str, str | None]:
    resolved = {field_name: None for field_name in field_names}
    for topic_name, field_name in topic_to_field.items():
        resolved[field_name] = topic_name
    return resolved


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
        for message in reader.read_messages(topics=topics):
            yield message.topic, int(message.timestamp), _normalize_payload(message.data)
        return

    for topic, timestamp, _msgtype, rawdata in reader.iter_raw_messages(topics=topics):
        yield topic, int(timestamp), _encode_raw_payload(rawdata)


def convert_no_resample(
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


def convert_downsample(
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


def collect_interpolation_samples(
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


def convert_interpolate(
    *,
    reader: RosReader,
    plan: TopicPlan,
    writer: Any,
    all_field_names: list[str],
    chunk_rows: int,
    freq_hz: float,
    use_normalized_payloads: bool,
) -> int:
    samples, min_ts, max_ts = collect_interpolation_samples(
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
