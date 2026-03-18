"""Service helpers for episode playback, timelines, and scrubber samples."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from hephaes._converter_helpers import _normalize_payload
from hephaes.models import Message
from hephaes.reader import RosReader

from app.db.models import Asset
from app.schemas.assets import TopicModality
from app.services.assets import (
    AssetEpisodeSummary,
    EpisodeDiscoveryUnavailableError,
    get_asset_or_raise,
    list_asset_episodes,
)

VISUAL_MODALITIES = {"image", "points", "scalar_series"}


class EpisodePlaybackError(Exception):
    """Base exception for episode playback failures."""


class EpisodeNotFoundError(EpisodePlaybackError):
    """Raised when an episode id is unknown for an asset."""


class EpisodeStreamNotFoundError(EpisodePlaybackError):
    """Raised when a requested stream id is unknown for an episode."""


@dataclass(frozen=True)
class EpisodeStreamSummary:
    """Resolved episode stream metadata used by phase 8 playback APIs."""

    id: str
    stream_key: str
    source_topic: str
    message_type: str
    modality: TopicModality
    message_count: int
    rate_hz: float
    first_timestamp_ns: int | None
    last_timestamp_ns: int | None
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class EpisodeDetail:
    """Episode detail surface used by the playback routes."""

    asset_id: str
    episode_id: str
    label: str
    source_kind: str
    start_time: datetime | None
    end_time: datetime | None
    start_timestamp_ns: int | None
    end_timestamp_ns: int | None
    duration_seconds: float
    has_visualizable_streams: bool
    default_lane_count: int
    streams: list[EpisodeStreamSummary]


@dataclass(frozen=True)
class EpisodeTimelineBucket:
    """Bucketed event-count summary for one timeline lane."""

    bucket_index: int
    start_offset_ns: int
    end_offset_ns: int
    event_count: int


@dataclass(frozen=True)
class EpisodeTimelineLane:
    """Timeline lane for one episode stream."""

    stream_id: str
    stream_key: str
    source_topic: str
    modality: TopicModality
    message_count: int
    first_timestamp_ns: int | None
    last_timestamp_ns: int | None
    non_empty_bucket_count: int
    buckets: list[EpisodeTimelineBucket]


@dataclass(frozen=True)
class EpisodeTimelineResult:
    """Timeline payload for scrubber rendering."""

    asset_id: str
    episode_id: str
    start_timestamp_ns: int | None
    end_timestamp_ns: int | None
    duration_ns: int
    bucket_count: int
    lanes: list[EpisodeTimelineLane]


@dataclass(frozen=True)
class EpisodeSampleData:
    """One synchronized sample returned to the frontend."""

    timestamp_ns: int
    payload: Any
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class EpisodeStreamSamples:
    """Sample collection for one selected episode stream."""

    stream_id: str
    stream_key: str
    source_topic: str
    modality: TopicModality
    selection_strategy: str
    samples: list[EpisodeSampleData]


@dataclass(frozen=True)
class EpisodeSamplesResult:
    """Top-level synchronized sample response."""

    asset_id: str
    episode_id: str
    requested_timestamp_ns: int
    window_before_ns: int
    window_after_ns: int
    window_start_ns: int
    window_end_ns: int
    streams: list[EpisodeStreamSamples]


def open_asset_reader(file_path: str) -> RosReader:
    """Open a RosReader for a registered asset path."""

    return RosReader.open(file_path)


def _datetime_to_timestamp_ns(value: datetime | None) -> int | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return int(value.timestamp() * 1_000_000_000)


def _stream_seed_from_topic(
    episode_id: str,
    *,
    topic_index: int,
    topic_payload: dict[str, Any],
) -> EpisodeStreamSummary:
    modality = str(topic_payload.get("modality", "other"))
    return EpisodeStreamSummary(
        id=f"{episode_id}:stream:{topic_index + 1}",
        stream_key=f"stream-{topic_index + 1}",
        source_topic=str(topic_payload["name"]),
        message_type=str(topic_payload["message_type"]),
        modality=modality,  # type: ignore[arg-type]
        message_count=int(topic_payload.get("message_count", 0)),
        rate_hz=float(topic_payload.get("rate_hz", 0.0)),
        first_timestamp_ns=None,
        last_timestamp_ns=None,
        metadata_json={
            "topic_index": topic_index,
            "visualizable": modality in VISUAL_MODALITIES,
        },
    )


def _resolve_stream_bounds(
    asset: Asset,
    *,
    streams: list[EpisodeStreamSummary],
) -> list[EpisodeStreamSummary]:
    if not streams:
        return []

    first_by_topic: dict[str, int] = {}
    last_by_topic: dict[str, int] = {}
    target_topics = [stream.source_topic for stream in streams]

    try:
        with open_asset_reader(asset.file_path) as reader:
            for topic, timestamp in reader.iter_message_headers(topics=target_topics):
                if topic not in first_by_topic:
                    first_by_topic[topic] = timestamp
                last_by_topic[topic] = timestamp
    except Exception as exc:
        raise EpisodePlaybackError(
            f"could not read episode stream headers for asset: {asset.file_name}"
        ) from exc

    return [
        replace(
            stream,
            first_timestamp_ns=first_by_topic.get(stream.source_topic),
            last_timestamp_ns=last_by_topic.get(stream.source_topic),
        )
        for stream in streams
    ]


def _episode_summary_for_asset(asset: Asset, episode_id: str) -> AssetEpisodeSummary:
    for episode in list_asset_episodes(asset):
        if episode.episode_id == episode_id:
            return episode
    raise EpisodeNotFoundError(f"episode not found: {episode_id}")


def _build_streams_for_episode(asset: Asset, episode_id: str) -> list[EpisodeStreamSummary]:
    metadata_record = asset.metadata_record
    if metadata_record is None:
        raise EpisodeDiscoveryUnavailableError(
            f"asset must be indexed before episodes are available: {asset.file_name}"
        )

    base_streams = [
        _stream_seed_from_topic(episode_id, topic_index=index, topic_payload=topic_payload)
        for index, topic_payload in enumerate(metadata_record.topics_json)
    ]
    return _resolve_stream_bounds(asset, streams=base_streams)


def _episode_bounds(
    episode: AssetEpisodeSummary,
    streams: list[EpisodeStreamSummary],
) -> tuple[int | None, int | None]:
    start_timestamp_ns = _datetime_to_timestamp_ns(episode.start_time)
    end_timestamp_ns = _datetime_to_timestamp_ns(episode.end_time)

    stream_firsts = [value for value in (stream.first_timestamp_ns for stream in streams) if value is not None]
    stream_lasts = [value for value in (stream.last_timestamp_ns for stream in streams) if value is not None]

    if start_timestamp_ns is None and stream_firsts:
        start_timestamp_ns = min(stream_firsts)
    if end_timestamp_ns is None and stream_lasts:
        end_timestamp_ns = max(stream_lasts)

    if start_timestamp_ns is None and end_timestamp_ns is not None and episode.duration > 0:
        start_timestamp_ns = end_timestamp_ns - int(round(episode.duration * 1_000_000_000))
    if end_timestamp_ns is None and start_timestamp_ns is not None and episode.duration > 0:
        end_timestamp_ns = start_timestamp_ns + int(round(episode.duration * 1_000_000_000))

    if start_timestamp_ns is not None and end_timestamp_ns is not None and end_timestamp_ns < start_timestamp_ns:
        end_timestamp_ns = start_timestamp_ns

    return start_timestamp_ns, end_timestamp_ns


def _duration_ns(
    *,
    start_timestamp_ns: int | None,
    end_timestamp_ns: int | None,
    duration_seconds: float,
) -> int:
    if start_timestamp_ns is not None and end_timestamp_ns is not None:
        return max(0, end_timestamp_ns - start_timestamp_ns)
    return max(0, int(round(duration_seconds * 1_000_000_000)))


def _select_streams(
    streams: list[EpisodeStreamSummary],
    *,
    stream_ids: list[str] | None,
) -> list[EpisodeStreamSummary]:
    if not stream_ids:
        return streams

    stream_by_id = {stream.id: stream for stream in streams}
    selected_streams: list[EpisodeStreamSummary] = []
    missing_stream_ids: list[str] = []

    for stream_id in stream_ids:
        stream = stream_by_id.get(stream_id)
        if stream is None:
            missing_stream_ids.append(stream_id)
            continue
        if stream not in selected_streams:
            selected_streams.append(stream)

    if missing_stream_ids:
        joined = ", ".join(missing_stream_ids)
        raise EpisodeStreamNotFoundError(f"episode stream not found: {joined}")

    return selected_streams


def _build_episode_detail(asset: Asset, episode: AssetEpisodeSummary) -> EpisodeDetail:
    metadata_record = asset.metadata_record
    if metadata_record is None:
        raise EpisodeDiscoveryUnavailableError(
            f"asset must be indexed before episodes are available: {asset.file_name}"
        )

    streams = _build_streams_for_episode(asset, episode.episode_id)
    start_timestamp_ns, end_timestamp_ns = _episode_bounds(episode, streams)
    visualization_summary = metadata_record.visualization_summary_json or {}

    return EpisodeDetail(
        asset_id=asset.id,
        episode_id=episode.episode_id,
        label=episode.label,
        source_kind="indexed_metadata",
        start_time=episode.start_time,
        end_time=episode.end_time,
        start_timestamp_ns=start_timestamp_ns,
        end_timestamp_ns=end_timestamp_ns,
        duration_seconds=episode.duration,
        has_visualizable_streams=bool(visualization_summary.get("has_visualizable_streams", False)),
        default_lane_count=int(visualization_summary.get("default_lane_count", 0)),
        streams=streams,
    )


def get_episode_detail(session: Session, asset_id: str, episode_id: str) -> EpisodeDetail:
    asset = get_asset_or_raise(session, asset_id)
    episode = _episode_summary_for_asset(asset, episode_id)
    return _build_episode_detail(asset, episode)


def _bucket_index(
    timestamp_ns: int,
    *,
    start_timestamp_ns: int,
    end_timestamp_ns: int | None,
    bucket_count: int,
) -> int:
    if bucket_count <= 1:
        return 0
    if end_timestamp_ns is None or end_timestamp_ns <= start_timestamp_ns:
        return 0

    duration_ns = end_timestamp_ns - start_timestamp_ns
    clamped_timestamp = max(start_timestamp_ns, min(timestamp_ns, end_timestamp_ns))
    offset_ns = clamped_timestamp - start_timestamp_ns
    index = (offset_ns * bucket_count) // duration_ns
    return min(bucket_count - 1, max(0, index))


def get_episode_timeline(
    session: Session,
    asset_id: str,
    episode_id: str,
    *,
    bucket_count: int = 120,
    stream_ids: list[str] | None = None,
) -> EpisodeTimelineResult:
    asset = get_asset_or_raise(session, asset_id)
    episode = _episode_summary_for_asset(asset, episode_id)
    detail = _build_episode_detail(asset, episode)
    selected_streams = _select_streams(detail.streams, stream_ids=stream_ids)

    counts_by_stream_id = {stream.id: [0] * bucket_count for stream in selected_streams}
    topic_to_stream = {stream.source_topic: stream for stream in selected_streams}

    if topic_to_stream and detail.start_timestamp_ns is not None:
        try:
            with open_asset_reader(asset.file_path) as reader:
                for topic, timestamp in reader.iter_message_headers(topics=list(topic_to_stream)):
                    stream = topic_to_stream.get(topic)
                    if stream is None:
                        continue
                    bucket_index = _bucket_index(
                        timestamp,
                        start_timestamp_ns=detail.start_timestamp_ns,
                        end_timestamp_ns=detail.end_timestamp_ns,
                        bucket_count=bucket_count,
                    )
                    counts_by_stream_id[stream.id][bucket_index] += 1
        except Exception as exc:
            raise EpisodePlaybackError(
                f"could not build episode timeline for asset: {asset.file_name}"
            ) from exc

    duration_ns = _duration_ns(
        start_timestamp_ns=detail.start_timestamp_ns,
        end_timestamp_ns=detail.end_timestamp_ns,
        duration_seconds=detail.duration_seconds,
    )

    lanes = []
    for stream in selected_streams:
        bucket_counts = counts_by_stream_id[stream.id]
        buckets = [
            EpisodeTimelineBucket(
                bucket_index=index,
                start_offset_ns=(duration_ns * index) // bucket_count if bucket_count else 0,
                end_offset_ns=(duration_ns * (index + 1)) // bucket_count if bucket_count else 0,
                event_count=event_count,
            )
            for index, event_count in enumerate(bucket_counts)
        ]
        lanes.append(
            EpisodeTimelineLane(
                stream_id=stream.id,
                stream_key=stream.stream_key,
                source_topic=stream.source_topic,
                modality=stream.modality,
                message_count=stream.message_count,
                first_timestamp_ns=stream.first_timestamp_ns,
                last_timestamp_ns=stream.last_timestamp_ns,
                non_empty_bucket_count=sum(1 for count in bucket_counts if count > 0),
                buckets=buckets,
            )
        )

    return EpisodeTimelineResult(
        asset_id=asset.id,
        episode_id=detail.episode_id,
        start_timestamp_ns=detail.start_timestamp_ns,
        end_timestamp_ns=detail.end_timestamp_ns,
        duration_ns=duration_ns,
        bucket_count=bucket_count,
        lanes=lanes,
    )


def _sample_metadata_for_payload(modality: TopicModality, payload: Any) -> dict[str, Any]:
    metadata_json: dict[str, Any] = {}
    if not isinstance(payload, dict):
        metadata_json["payload_type"] = type(payload).__name__
        return metadata_json

    if modality == "image":
        for key in ("width", "height", "encoding", "step", "frame_id"):
            if key in payload:
                metadata_json[key] = payload[key]
        if "data" in payload and isinstance(payload["data"], dict):
            metadata_json["has_inline_data"] = True
    elif modality == "points":
        for key in ("frame_id", "point_step", "row_step", "is_dense"):
            if key in payload:
                metadata_json[key] = payload[key]
        if isinstance(payload.get("points"), list):
            metadata_json["point_count"] = len(payload["points"])
        elif isinstance(payload.get("ranges"), list):
            metadata_json["point_count"] = len(payload["ranges"])
    elif modality == "scalar_series":
        metadata_json["payload_type"] = "scalar_series"
    else:
        metadata_json["payload_type"] = "other"

    return metadata_json


def _sample_from_message(stream: EpisodeStreamSummary, message: Message) -> EpisodeSampleData:
    normalized_payload = _normalize_payload(message.data)
    return EpisodeSampleData(
        timestamp_ns=message.timestamp,
        payload=normalized_payload,
        metadata_json=_sample_metadata_for_payload(stream.modality, normalized_payload),
    )


def get_episode_samples(
    session: Session,
    asset_id: str,
    episode_id: str,
    *,
    timestamp_ns: int,
    window_before_ns: int = 0,
    window_after_ns: int = 0,
    stream_ids: list[str] | None = None,
) -> EpisodeSamplesResult:
    asset = get_asset_or_raise(session, asset_id)
    episode = _episode_summary_for_asset(asset, episode_id)
    detail = _build_episode_detail(asset, episode)
    selected_streams = _select_streams(detail.streams, stream_ids=stream_ids)

    window_start_ns = max(0, timestamp_ns - window_before_ns)
    window_end_ns = timestamp_ns + window_after_ns
    has_window = window_before_ns > 0 or window_after_ns > 0

    scalar_window_samples: dict[str, list[EpisodeSampleData]] = {
        stream.id: [] for stream in selected_streams if stream.modality == "scalar_series"
    }
    nearest_samples: dict[str, tuple[int, EpisodeSampleData]] = {}
    topic_to_stream = {stream.source_topic: stream for stream in selected_streams}

    if topic_to_stream:
        try:
            with open_asset_reader(asset.file_path) as reader:
                for message in reader.read_messages(topics=list(topic_to_stream)):
                    stream = topic_to_stream.get(message.topic)
                    if stream is None:
                        continue

                    if stream.modality == "scalar_series" and has_window:
                        if window_start_ns <= message.timestamp <= window_end_ns:
                            scalar_window_samples[stream.id].append(
                                _sample_from_message(stream, message)
                            )
                        continue

                    if has_window and not (window_start_ns <= message.timestamp <= window_end_ns):
                        continue

                    candidate = _sample_from_message(stream, message)
                    distance = abs(message.timestamp - timestamp_ns)
                    previous = nearest_samples.get(stream.id)
                    if previous is None or distance < previous[0]:
                        nearest_samples[stream.id] = (distance, candidate)
        except Exception as exc:
            raise EpisodePlaybackError(
                f"could not read episode samples for asset: {asset.file_name}"
            ) from exc

    stream_results: list[EpisodeStreamSamples] = []
    for stream in selected_streams:
        if stream.modality == "scalar_series" and has_window:
            samples = sorted(
                scalar_window_samples.get(stream.id, []),
                key=lambda item: item.timestamp_ns,
            )
            selection_strategy = "window"
        else:
            nearest = nearest_samples.get(stream.id)
            samples = [nearest[1]] if nearest is not None else []
            selection_strategy = "nearest"

        stream_results.append(
            EpisodeStreamSamples(
                stream_id=stream.id,
                stream_key=stream.stream_key,
                source_topic=stream.source_topic,
                modality=stream.modality,
                selection_strategy=selection_strategy,
                samples=samples,
            )
        )

    return EpisodeSamplesResult(
        asset_id=asset.id,
        episode_id=detail.episode_id,
        requested_timestamp_ns=timestamp_ns,
        window_before_ns=window_before_ns,
        window_after_ns=window_after_ns,
        window_start_ns=window_start_ns,
        window_end_ns=window_end_ns,
        streams=stream_results,
    )
