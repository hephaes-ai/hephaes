"""Episode playback routes for the backend application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
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
    EpisodeDetail,
    EpisodeNotFoundError,
    EpisodePlaybackError,
    EpisodeStreamNotFoundError,
    get_episode_detail,
    get_episode_samples,
    get_episode_timeline,
)

router = APIRouter(prefix="/assets/{asset_id}/episodes", tags=["episodes"])
DbSession = Annotated[Session, Depends(get_db_session)]


@dataclass
class ReplaySessionState:
    cursor_ns: int | None = None
    is_playing: bool = False
    speed: float = 1.0
    stream_ids: list[str] | None = None
    window_before_ns: int = 0
    window_after_ns: int = 0
    last_revision: int = -1


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


def _build_episode_samples_response(samples) -> EpisodeSamplesResponse:
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
                selection_strategy=stream.selection_strategy,  # type: ignore[arg-type]
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


def _build_replay_ready_message(detail: EpisodeDetail) -> dict[str, object]:
    return {
        "type": "ready",
        "revision": 0,
        "asset_id": detail.asset_id,
        "episode_id": detail.episode_id,
        "stream_ids": [stream.id for stream in detail.streams],
        "window_before_ns": 0,
        "window_after_ns": 0,
        "is_playing": False,
        "speed": 1.0,
    }


def _validate_replay_stream_ids(detail: EpisodeDetail, stream_ids: list[str] | None) -> list[str] | None:
    if not stream_ids:
        return None

    available_stream_ids = {stream.id for stream in detail.streams}
    missing_stream_ids = [stream_id for stream_id in stream_ids if stream_id not in available_stream_ids]
    if missing_stream_ids:
        joined = ", ".join(missing_stream_ids)
        raise EpisodeStreamNotFoundError(f"episode stream not found: {joined}")

    return stream_ids


def _parse_replay_revision(payload: object) -> int:
    if not isinstance(payload, dict):
        raise ValueError("replay websocket payload must be an object")
    revision = payload.get("revision")
    if not isinstance(revision, int) or revision < 0:
        raise ValueError("replay websocket payload must include a non-negative integer revision")
    return revision


def _parse_replay_message_type(payload: object) -> str:
    if not isinstance(payload, dict):
        raise ValueError("replay websocket payload must be an object")
    message_type = payload.get("type")
    if not isinstance(message_type, str) or not message_type:
        raise ValueError("replay websocket payload must include a type")
    return message_type


def _parse_stream_ids_payload(value: object) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("stream_ids must be a list of strings")

    normalized_stream_ids: list[str] = []
    for raw_value in value:
        if not isinstance(raw_value, str):
            raise ValueError("stream_ids must contain only strings")
        stream_id = raw_value.strip()
        if stream_id:
            normalized_stream_ids.append(stream_id)
    return normalized_stream_ids or None


def _parse_non_negative_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{key} must be a non-negative integer")
    return value


def _parse_positive_number(payload: dict[str, object], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{key} must be a positive number")
    return float(value)


async def _send_replay_samples(
    websocket: WebSocket,
    *,
    session_factory,
    asset_id: str,
    episode_id: str,
    state: ReplaySessionState,
    revision: int,
    cursor_ns: int,
) -> None:
    with session_factory() as session:
        samples = get_episode_samples(
            session,
            asset_id,
            episode_id,
            timestamp_ns=cursor_ns,
            window_before_ns=state.window_before_ns,
            window_after_ns=state.window_after_ns,
            stream_ids=state.stream_ids,
        )

    response = _build_episode_samples_response(samples)
    await websocket.send_json(
        {
            "type": "cursor_ack",
            "revision": revision,
            "cursor_ns": cursor_ns,
        }
    )
    await websocket.send_json(
        {
            "type": "samples",
            "revision": revision,
            "cursor_ns": cursor_ns,
            "data": response.model_dump(mode="json"),
        }
    )


async def _send_playback_state(
    websocket: WebSocket,
    *,
    revision: int,
    state: ReplaySessionState,
) -> None:
    await websocket.send_json(
        {
            "type": "playback_state",
            "revision": revision,
            "is_playing": state.is_playing,
            "speed": state.speed,
        }
    )


async def _send_replay_error(websocket: WebSocket, *, revision: int | None, detail: str) -> None:
    await websocket.send_json(
        {
            "type": "error",
            "revision": revision,
            "detail": detail,
        }
    )


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

    return _build_episode_samples_response(samples)


@router.websocket("/{episode_id}/replay")
async def episode_replay_route(websocket: WebSocket, asset_id: str, episode_id: str) -> None:
    session_factory = getattr(websocket.app.state, "session_factory", None)
    await websocket.accept()

    if session_factory is None:
        await _send_replay_error(websocket, revision=None, detail="database session factory is not configured")
        await websocket.close(code=1011)
        return

    try:
        with session_factory() as session:
            detail = get_episode_detail(session, asset_id, episode_id)
    except (AssetNotFoundError, EpisodeNotFoundError, EpisodePlaybackError, EpisodeDiscoveryUnavailableError) as exc:
        await _send_replay_error(websocket, revision=None, detail=str(exc))
        await websocket.close(code=1008)
        return

    state = ReplaySessionState()
    await websocket.send_json(_build_replay_ready_message(detail))

    try:
        while True:
            payload = await websocket.receive_json()
            message_type = _parse_replay_message_type(payload)
            revision = _parse_replay_revision(payload)

            if revision <= state.last_revision:
                continue

            if not isinstance(payload, dict):
                raise ValueError("replay websocket payload must be an object")

            if message_type == "hello":
                state.last_revision = revision
                state.stream_ids = _validate_replay_stream_ids(
                    detail,
                    _parse_stream_ids_payload(payload.get("stream_ids")),
                )
                if "window_before_ns" in payload:
                    state.window_before_ns = _parse_non_negative_int(payload, "window_before_ns")
                if "window_after_ns" in payload:
                    state.window_after_ns = _parse_non_negative_int(payload, "window_after_ns")
                if "speed" in payload:
                    state.speed = _parse_positive_number(payload, "speed")
                if "is_playing" in payload:
                    is_playing = payload.get("is_playing")
                    if not isinstance(is_playing, bool):
                        raise ValueError("is_playing must be a boolean")
                    state.is_playing = is_playing

                await _send_playback_state(websocket, revision=revision, state=state)

                if "cursor_ns" in payload:
                    state.cursor_ns = _parse_non_negative_int(payload, "cursor_ns")
                    await _send_replay_samples(
                        websocket,
                        session_factory=session_factory,
                        asset_id=asset_id,
                        episode_id=episode_id,
                        state=state,
                        revision=revision,
                        cursor_ns=state.cursor_ns,
                    )
                continue

            if message_type == "seek":
                state.last_revision = revision
                state.cursor_ns = _parse_non_negative_int(payload, "cursor_ns")
                await _send_replay_samples(
                    websocket,
                    session_factory=session_factory,
                    asset_id=asset_id,
                    episode_id=episode_id,
                    state=state,
                    revision=revision,
                    cursor_ns=state.cursor_ns,
                )
                continue

            if message_type == "set_streams":
                state.last_revision = revision
                state.stream_ids = _validate_replay_stream_ids(
                    detail,
                    _parse_stream_ids_payload(payload.get("stream_ids")),
                )
                if state.cursor_ns is not None:
                    await _send_replay_samples(
                        websocket,
                        session_factory=session_factory,
                        asset_id=asset_id,
                        episode_id=episode_id,
                        state=state,
                        revision=revision,
                        cursor_ns=state.cursor_ns,
                    )
                continue

            if message_type == "set_scalar_window":
                state.last_revision = revision
                state.window_before_ns = _parse_non_negative_int(payload, "window_before_ns")
                state.window_after_ns = _parse_non_negative_int(payload, "window_after_ns")
                if state.cursor_ns is not None:
                    await _send_replay_samples(
                        websocket,
                        session_factory=session_factory,
                        asset_id=asset_id,
                        episode_id=episode_id,
                        state=state,
                        revision=revision,
                        cursor_ns=state.cursor_ns,
                    )
                continue

            if message_type == "play":
                state.last_revision = revision
                if "speed" in payload:
                    state.speed = _parse_positive_number(payload, "speed")
                state.is_playing = True
                await _send_playback_state(websocket, revision=revision, state=state)
                continue

            if message_type == "pause":
                state.last_revision = revision
                state.is_playing = False
                await _send_playback_state(websocket, revision=revision, state=state)
                continue

            if message_type == "set_speed":
                state.last_revision = revision
                state.speed = _parse_positive_number(payload, "speed")
                await _send_playback_state(websocket, revision=revision, state=state)
                continue

            raise ValueError(f"unsupported replay websocket message type: {message_type}")
    except WebSocketDisconnect:
        return
    except (AssetNotFoundError, EpisodeNotFoundError, EpisodePlaybackError, EpisodeDiscoveryUnavailableError, EpisodeStreamNotFoundError, ValueError) as exc:
        await _send_replay_error(
            websocket,
            revision=revision if "revision" in locals() else None,
            detail=str(exc),
        )
        await websocket.close(code=1008)
