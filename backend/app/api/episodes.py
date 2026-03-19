"""Episode playback routes for the backend application."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api._status import HTTP_422_UNPROCESSABLE_CONTENT
from app.db.session import get_db_session
from app.schemas.episodes import (
    EpisodeDetailResponse,
    EpisodeSampleDataResponse,
    EpisodeSamplesResponse,
    EpisodeStreamResponse,
    EpisodeStreamSamplesResponse,
    EpisodeTimelineBucketResponse,
    EpisodeTimelineLaneResponse,
    EpisodeTimelineResponse,
)
from app.services.assets import AssetNotFoundError, EpisodeDiscoveryUnavailableError
from app.services.episodes import (
    EpisodeNotFoundError,
    EpisodePlaybackError,
    EpisodeStreamNotFoundError,
    get_episode_detail,
    get_episode_samples,
    get_episode_timeline,
)

router = APIRouter(prefix="/assets/{asset_id}/episodes", tags=["episodes"])
DbSession = Annotated[Session, Depends(get_db_session)]


def _normalize_stream_ids(raw_stream_ids: list[str] | None) -> list[str] | None:
    if not raw_stream_ids:
        return None

    normalized_stream_ids: list[str] = []
    for raw_value in raw_stream_ids:
        for candidate in raw_value.split(","):
            stream_id = candidate.strip()
            if stream_id:
                normalized_stream_ids.append(stream_id)

    return normalized_stream_ids or None


@router.get("/{episode_id}", response_model=EpisodeDetailResponse)
def get_episode_detail_route(asset_id: str, episode_id: str, session: DbSession) -> EpisodeDetailResponse:
    try:
        episode = get_episode_detail(session, asset_id, episode_id)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EpisodeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EpisodePlaybackError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except EpisodeDiscoveryUnavailableError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return EpisodeDetailResponse(
        asset_id=episode.asset_id,
        episode_id=episode.episode_id,
        label=episode.label,
        source_kind="indexed_metadata",
        start_time=episode.start_time,
        end_time=episode.end_time,
        start_timestamp_ns=episode.start_timestamp_ns,
        end_timestamp_ns=episode.end_timestamp_ns,
        duration_seconds=episode.duration_seconds,
        has_visualizable_streams=episode.has_visualizable_streams,
        default_lane_count=episode.default_lane_count,
        stream_count=len(episode.streams),
        streams=[
            EpisodeStreamResponse(
                id=stream.id,
                stream_key=stream.stream_key,
                source_topic=stream.source_topic,
                message_type=stream.message_type,
                modality=stream.modality,
                message_count=stream.message_count,
                rate_hz=stream.rate_hz,
                first_timestamp_ns=stream.first_timestamp_ns,
                last_timestamp_ns=stream.last_timestamp_ns,
                metadata_json=stream.metadata_json,
            )
            for stream in episode.streams
        ],
    )


@router.get("/{episode_id}/timeline", response_model=EpisodeTimelineResponse)
def get_episode_timeline_route(
    asset_id: str,
    episode_id: str,
    session: DbSession,
    bucket_count: Annotated[int, Query(ge=1, le=500)] = 120,
    stream_ids: Annotated[list[str] | None, Query()] = None,
) -> EpisodeTimelineResponse:
    try:
        timeline = get_episode_timeline(
            session,
            asset_id,
            episode_id,
            bucket_count=bucket_count,
            stream_ids=_normalize_stream_ids(stream_ids),
        )
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EpisodeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EpisodeStreamNotFoundError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except EpisodePlaybackError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except EpisodeDiscoveryUnavailableError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return EpisodeTimelineResponse(
        asset_id=timeline.asset_id,
        episode_id=timeline.episode_id,
        start_timestamp_ns=timeline.start_timestamp_ns,
        end_timestamp_ns=timeline.end_timestamp_ns,
        duration_ns=timeline.duration_ns,
        bucket_count=timeline.bucket_count,
        lanes=[
            EpisodeTimelineLaneResponse(
                stream_id=lane.stream_id,
                stream_key=lane.stream_key,
                source_topic=lane.source_topic,
                modality=lane.modality,
                message_count=lane.message_count,
                first_timestamp_ns=lane.first_timestamp_ns,
                last_timestamp_ns=lane.last_timestamp_ns,
                non_empty_bucket_count=lane.non_empty_bucket_count,
                buckets=[
                    EpisodeTimelineBucketResponse(
                        bucket_index=bucket.bucket_index,
                        start_offset_ns=bucket.start_offset_ns,
                        end_offset_ns=bucket.end_offset_ns,
                        event_count=bucket.event_count,
                    )
                    for bucket in lane.buckets
                ],
            )
            for lane in timeline.lanes
        ],
    )


@router.get("/{episode_id}/samples", response_model=EpisodeSamplesResponse)
def get_episode_samples_route(
    asset_id: str,
    episode_id: str,
    session: DbSession,
    timestamp_ns: Annotated[int, Query(ge=0)],
    window_before_ns: Annotated[int, Query(ge=0)] = 0,
    window_after_ns: Annotated[int, Query(ge=0)] = 0,
    stream_ids: Annotated[list[str] | None, Query()] = None,
) -> EpisodeSamplesResponse:
    try:
        samples = get_episode_samples(
            session,
            asset_id,
            episode_id,
            timestamp_ns=timestamp_ns,
            window_before_ns=window_before_ns,
            window_after_ns=window_after_ns,
            stream_ids=_normalize_stream_ids(stream_ids),
        )
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EpisodeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EpisodeStreamNotFoundError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except EpisodePlaybackError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except EpisodeDiscoveryUnavailableError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return EpisodeSamplesResponse(
        asset_id=samples.asset_id,
        episode_id=samples.episode_id,
        requested_timestamp_ns=samples.requested_timestamp_ns,
        window_before_ns=samples.window_before_ns,
        window_after_ns=samples.window_after_ns,
        window_start_ns=samples.window_start_ns,
        window_end_ns=samples.window_end_ns,
        streams=[
            EpisodeStreamSamplesResponse(
                stream_id=stream.stream_id,
                stream_key=stream.stream_key,
                source_topic=stream.source_topic,
                modality=stream.modality,
                selection_strategy=stream.selection_strategy,
                sample_count=len(stream.samples),
                samples=[
                    EpisodeSampleDataResponse(
                        timestamp_ns=sample.timestamp_ns,
                        payload=sample.payload,
                        metadata_json=sample.metadata_json,
                    )
                    for sample in stream.samples
                ],
            )
            for stream in samples.streams
        ],
    )
