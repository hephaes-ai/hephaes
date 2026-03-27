from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime

from ._workspace_models import (
    DefaultEpisodeSummary,
    IndexedAssetMetadata,
    IndexedTopicSummary,
    IndexMetadataPayload,
    RegisteredAsset,
    SourceAssetMetadata,
    VisualizationSummary,
)


def to_db_timestamp(value: datetime) -> str:
    return value.isoformat()


def from_db_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def row_to_registered_asset(row: sqlite3.Row) -> RegisteredAsset:
    return RegisteredAsset(
        id=row["id"],
        file_path=row["file_path"],
        file_name=row["file_name"],
        file_type=row["file_type"],
        file_size=int(row["file_size"]),
        registered_at=from_db_timestamp(row["registered_at"]),
        updated_at=from_db_timestamp(row["updated_at"]),
        indexing_status=row["indexing_status"],
        last_indexed_at=(
            from_db_timestamp(row["last_indexed_at"])
            if row["last_indexed_at"] is not None
            else None
        ),
    )


def row_to_indexed_asset_metadata(row: sqlite3.Row) -> IndexedAssetMetadata:
    return IndexedAssetMetadata(
        asset_id=row["asset_id"],
        duration=row["duration"],
        start_time=from_db_timestamp(row["start_time"]) if row["start_time"] is not None else None,
        end_time=from_db_timestamp(row["end_time"]) if row["end_time"] is not None else None,
        topic_count=int(row["topic_count"]),
        message_count=int(row["message_count"]),
        sensor_types=list(json.loads(row["sensor_types_json"])),
        topics=[
            IndexedTopicSummary(**topic_payload)
            for topic_payload in json.loads(row["topics_json"])
        ],
        default_episode=(
            DefaultEpisodeSummary(**json.loads(row["default_episode_json"]))
            if row["default_episode_json"] is not None
            else None
        ),
        visualization_summary=(
            VisualizationSummary(**json.loads(row["visualization_summary_json"]))
            if row["visualization_summary_json"] is not None
            else None
        ),
        raw_metadata=(
            SourceAssetMetadata(**json.loads(row["raw_metadata_json"]))
            if row["raw_metadata_json"] not in (None, "{}", "")
            else None
        ),
        indexing_error=row["indexing_error"],
        created_at=from_db_timestamp(row["created_at"]),
        updated_at=from_db_timestamp(row["updated_at"]),
    )


def upsert_asset_metadata(
    connection: sqlite3.Connection,
    *,
    asset_id: str,
    payload: IndexMetadataPayload | None,
    indexing_error: str | None,
    timestamp: datetime,
) -> None:
    existing = connection.execute(
        "SELECT created_at FROM asset_metadata WHERE asset_id = ?",
        (asset_id,),
    ).fetchone()
    created_at = existing["created_at"] if existing is not None else to_db_timestamp(timestamp)

    if payload is None and existing is not None:
        connection.execute(
            """
            UPDATE asset_metadata
            SET indexing_error = ?, updated_at = ?
            WHERE asset_id = ?
            """,
            (
                indexing_error,
                to_db_timestamp(timestamp),
                asset_id,
            ),
        )
        return

    default_episode_json = (
        json.dumps(asdict(payload.default_episode))
        if payload is not None and payload.default_episode is not None
        else None
    )
    visualization_summary_json = (
        json.dumps(asdict(payload.visualization_summary))
        if payload is not None and payload.visualization_summary is not None
        else None
    )
    raw_metadata_json = (
        json.dumps(asdict(payload.raw_metadata))
        if payload is not None
        else json.dumps({})
    )
    topics_json = (
        json.dumps([asdict(topic) for topic in payload.topics])
        if payload is not None
        else json.dumps([])
    )
    sensor_types_json = (
        json.dumps(payload.sensor_types)
        if payload is not None
        else json.dumps([])
    )

    connection.execute(
        """
        INSERT INTO asset_metadata(
            asset_id,
            duration,
            start_time,
            end_time,
            topic_count,
            message_count,
            sensor_types_json,
            topics_json,
            default_episode_json,
            visualization_summary_json,
            raw_metadata_json,
            indexing_error,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(asset_id) DO UPDATE SET
            duration = excluded.duration,
            start_time = excluded.start_time,
            end_time = excluded.end_time,
            topic_count = excluded.topic_count,
            message_count = excluded.message_count,
            sensor_types_json = excluded.sensor_types_json,
            topics_json = excluded.topics_json,
            default_episode_json = excluded.default_episode_json,
            visualization_summary_json = excluded.visualization_summary_json,
            raw_metadata_json = excluded.raw_metadata_json,
            indexing_error = excluded.indexing_error,
            updated_at = excluded.updated_at
        """,
        (
            asset_id,
            payload.duration if payload is not None else None,
            to_db_timestamp(payload.start_time) if payload is not None and payload.start_time is not None else None,
            to_db_timestamp(payload.end_time) if payload is not None and payload.end_time is not None else None,
            payload.topic_count if payload is not None else 0,
            payload.message_count if payload is not None else 0,
            sensor_types_json,
            topics_json,
            default_episode_json,
            visualization_summary_json,
            raw_metadata_json,
            indexing_error,
            created_at,
            to_db_timestamp(timestamp),
        ),
    )
