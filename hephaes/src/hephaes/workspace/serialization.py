from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime

from .models import (
    ConversionDraft,
    ConversionDraftRevision,
    ConversionDraftRevisionSummary,
    ConversionDraftSummary,
    DefaultEpisodeSummary,
    IndexedAssetMetadata,
    IndexedTopicSummary,
    IndexMetadataPayload,
    OutputArtifact,
    OutputArtifactSummary,
    RegisteredAsset,
    SavedConversionConfig,
    SavedConversionConfigRevision,
    SavedConversionConfigRevisionSummary,
    SavedConversionConfigSummary,
    SourceAssetMetadata,
    VisualizationSummary,
    ConversionRun,
    WorkspaceTag,
    WorkspaceJob,
)
from ..conversion.spec_io import ConversionSpecDocument


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


def row_to_workspace_tag(row: sqlite3.Row) -> WorkspaceTag:
    return WorkspaceTag(
        id=row["id"],
        name=row["name"],
        created_at=from_db_timestamp(row["created_at"]),
        updated_at=from_db_timestamp(row["updated_at"]),
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


def row_to_saved_conversion_config_summary(
    row: sqlite3.Row,
    *,
    document_path: str,
) -> SavedConversionConfigSummary:
    return SavedConversionConfigSummary(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        metadata=dict(json.loads(row["metadata_json"])),
        spec_document_version=int(row["spec_document_version"]),
        document_path=document_path,
        created_at=from_db_timestamp(row["created_at"]),
        updated_at=from_db_timestamp(row["updated_at"]),
        last_opened_at=(
            from_db_timestamp(row["last_opened_at"])
            if row["last_opened_at"] is not None
            else None
        ),
        invalid_reason=row["invalid_reason"],
    )


def build_saved_conversion_config(
    summary: SavedConversionConfigSummary,
    *,
    document: ConversionSpecDocument,
) -> SavedConversionConfig:
    return SavedConversionConfig(
        id=summary.id,
        name=summary.name,
        description=summary.description,
        metadata=summary.metadata,
        document=document,
        spec_document_version=summary.spec_document_version,
        document_path=summary.document_path,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
        last_opened_at=summary.last_opened_at,
        invalid_reason=summary.invalid_reason,
    )


def row_to_saved_conversion_config_revision_summary(
    row: sqlite3.Row,
    *,
    document_path: str,
) -> SavedConversionConfigRevisionSummary:
    return SavedConversionConfigRevisionSummary(
        id=row["id"],
        config_id=row["config_id"],
        revision_number=int(row["revision_number"]),
        description=row["description"],
        metadata=dict(json.loads(row["metadata_json"])),
        spec_document_version=int(row["spec_document_version"]),
        document_path=document_path,
        created_at=from_db_timestamp(row["created_at"]),
        invalid_reason=row["invalid_reason"],
    )


def build_saved_conversion_config_revision(
    summary: SavedConversionConfigRevisionSummary,
    *,
    document: ConversionSpecDocument,
) -> SavedConversionConfigRevision:
    return SavedConversionConfigRevision(
        id=summary.id,
        config_id=summary.config_id,
        revision_number=summary.revision_number,
        description=summary.description,
        metadata=summary.metadata,
        document=document,
        spec_document_version=summary.spec_document_version,
        document_path=summary.document_path,
        created_at=summary.created_at,
        invalid_reason=summary.invalid_reason,
    )


def row_to_conversion_draft_summary(row: sqlite3.Row) -> ConversionDraftSummary:
    return ConversionDraftSummary(
        id=row["id"],
        source_asset_id=row["source_asset_id"],
        status=row["status"],
        current_revision_id=row["current_revision_id"],
        confirmed_revision_id=row["confirmed_revision_id"],
        saved_config_id=row["saved_config_id"],
        created_at=from_db_timestamp(row["created_at"]),
        updated_at=from_db_timestamp(row["updated_at"]),
        discarded_at=(
            from_db_timestamp(row["discarded_at"])
            if row["discarded_at"] is not None
            else None
        ),
    )


def build_conversion_draft(
    summary: ConversionDraftSummary,
    *,
    current_revision: ConversionDraftRevision | None,
    confirmed_revision: ConversionDraftRevision | None,
) -> ConversionDraft:
    return ConversionDraft(
        id=summary.id,
        source_asset_id=summary.source_asset_id,
        status=summary.status,
        current_revision_id=summary.current_revision_id,
        confirmed_revision_id=summary.confirmed_revision_id,
        saved_config_id=summary.saved_config_id,
        current_revision=current_revision,
        confirmed_revision=confirmed_revision,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
        discarded_at=summary.discarded_at,
    )


def row_to_conversion_draft_revision_summary(
    row: sqlite3.Row,
    *,
    document_path: str,
) -> ConversionDraftRevisionSummary:
    return ConversionDraftRevisionSummary(
        draft_id=row["draft_id"],
        id=row["id"],
        revision_number=int(row["revision_number"]),
        label=row["label"],
        saved_config_id=row["saved_config_id"],
        source_asset_id=row["source_asset_id"],
        status=row["status"],
        metadata=dict(json.loads(row["metadata_json"])),
        inspection_request_json=dict(json.loads(row["inspection_request_json"])),
        inspection_json=dict(json.loads(row["inspection_json"])),
        draft_request_json=dict(json.loads(row["draft_request_json"])),
        draft_result_json=dict(json.loads(row["draft_result_json"])),
        preview_request_json=dict(json.loads(row["preview_request_json"])),
        preview_json=(
            dict(json.loads(row["preview_json"]))
            if row["preview_json"] is not None
            else None
        ),
        spec_document_version=int(row["spec_document_version"]),
        document_path=document_path,
        created_at=from_db_timestamp(row["created_at"]),
        updated_at=from_db_timestamp(row["updated_at"]),
        invalid_reason=row["invalid_reason"],
    )


def build_conversion_draft_revision(
    summary: ConversionDraftRevisionSummary,
    *,
    document: ConversionSpecDocument,
) -> ConversionDraftRevision:
    return ConversionDraftRevision(
        draft_id=summary.draft_id,
        id=summary.id,
        revision_number=summary.revision_number,
        label=summary.label,
        saved_config_id=summary.saved_config_id,
        source_asset_id=summary.source_asset_id,
        status=summary.status,
        metadata=summary.metadata,
        inspection_request_json=summary.inspection_request_json,
        inspection_json=summary.inspection_json,
        draft_request_json=summary.draft_request_json,
        draft_result_json=summary.draft_result_json,
        preview_request_json=summary.preview_request_json,
        preview_json=summary.preview_json,
        document=document,
        spec_document_version=summary.spec_document_version,
        document_path=summary.document_path,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
        invalid_reason=summary.invalid_reason,
    )


def row_to_workspace_job(row: sqlite3.Row) -> WorkspaceJob:
    return WorkspaceJob(
        id=row["id"],
        kind=row["kind"],
        status=row["status"],
        target_asset_ids=list(json.loads(row["target_asset_ids_json"])),
        config=dict(json.loads(row["config_json"])),
        conversion_run_id=row["conversion_run_id"],
        error_message=row["error_message"],
        created_at=from_db_timestamp(row["created_at"]),
        updated_at=from_db_timestamp(row["updated_at"]),
        started_at=(
            from_db_timestamp(row["started_at"])
            if row["started_at"] is not None
            else None
        ),
        completed_at=(
            from_db_timestamp(row["completed_at"])
            if row["completed_at"] is not None
            else None
        ),
    )


def row_to_conversion_run(row: sqlite3.Row) -> ConversionRun:
    return ConversionRun(
        id=row["id"],
        job_id=row["job_id"],
        status=row["status"],
        source_asset_ids=list(json.loads(row["source_asset_ids_json"])),
        source_asset_paths=list(json.loads(row["source_asset_paths_json"])),
        saved_config_id=row["saved_config_id"],
        saved_config_revision_id=row["saved_config_revision_id"],
        config=dict(json.loads(row["config_json"])),
        output_dir=row["output_dir"],
        output_paths=list(json.loads(row["output_paths_json"])),
        error_message=row["error_message"],
        created_at=from_db_timestamp(row["created_at"]),
        updated_at=from_db_timestamp(row["updated_at"]),
        started_at=(
            from_db_timestamp(row["started_at"])
            if row["started_at"] is not None
            else None
        ),
        completed_at=(
            from_db_timestamp(row["completed_at"])
            if row["completed_at"] is not None
            else None
        ),
    )


def row_to_output_artifact(row: sqlite3.Row) -> OutputArtifact:
    return OutputArtifact(
        id=row["id"],
        conversion_run_id=row["conversion_run_id"],
        source_asset_id=row["source_asset_id"],
        source_asset_path=row["source_asset_path"],
        output_path=row["output_path"],
        relative_path=row["relative_path"],
        file_name=row["file_name"],
        format=row["format"],
        role=row["role"],
        size_bytes=int(row["size_bytes"]),
        availability_status=row["availability_status"],
        media_type=row["media_type"],
        metadata=dict(json.loads(row["metadata_json"])),
        created_at=from_db_timestamp(row["created_at"]),
        updated_at=from_db_timestamp(row["updated_at"]),
        saved_config_id=row["saved_config_id"],
        manifest_available=bool(row["manifest_available"]),
        report_available=bool(row["report_available"]),
    )


def row_to_output_artifact_summary(row: sqlite3.Row) -> OutputArtifactSummary:
    artifact = row_to_output_artifact(row)
    return OutputArtifactSummary(
        id=artifact.id,
        conversion_run_id=artifact.conversion_run_id,
        source_asset_id=artifact.source_asset_id,
        source_asset_path=artifact.source_asset_path,
        output_path=artifact.output_path,
        format=artifact.format,
        role=artifact.role,
        created_at=artifact.created_at,
        saved_config_id=artifact.saved_config_id,
        manifest_available=artifact.manifest_available,
        report_available=artifact.report_available,
    )
