from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from .metrics import SensorFamily, TopicModality
from .conversion.spec_io import ConversionSpecDocument
from .models import CompressionFormat, RosVersion, StorageFormat

AssetRegistrationMode = Literal["error", "skip", "refresh"]


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path
    workspace_dir: Path
    database_path: Path
    imports_dir: Path
    outputs_dir: Path
    specs_dir: Path
    spec_revisions_dir: Path
    draft_revisions_dir: Path
    jobs_dir: Path


@dataclass(frozen=True)
class RegisteredAsset:
    id: str
    file_path: str
    source_path: str | None
    file_name: str
    file_type: str
    file_size: int
    imported_at: datetime
    registered_at: datetime
    updated_at: datetime
    indexing_status: str
    last_indexed_at: datetime | None


@dataclass(frozen=True)
class WorkspaceTag:
    id: str
    name: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class IndexedTopicSummary:
    name: str
    message_type: str
    message_count: int
    rate_hz: float
    modality: TopicModality


@dataclass(frozen=True)
class DefaultEpisodeSummary:
    episode_id: str
    label: str
    duration: float


@dataclass(frozen=True)
class VisualizationSummary:
    has_visualizable_streams: bool
    default_lane_count: int


@dataclass(frozen=True)
class SourceAssetMetadata:
    compression_format: CompressionFormat
    file_path: str
    file_size_bytes: int
    path: str
    ros_version: RosVersion
    storage_format: StorageFormat


@dataclass(frozen=True)
class IndexedAssetMetadata:
    asset_id: str
    duration: float | None
    start_time: datetime | None
    end_time: datetime | None
    topic_count: int
    message_count: int
    sensor_types: list[SensorFamily]
    topics: list[IndexedTopicSummary]
    default_episode: DefaultEpisodeSummary | None
    visualization_summary: VisualizationSummary | None
    raw_metadata: SourceAssetMetadata | None
    indexing_error: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class IndexMetadataPayload:
    duration: float | None
    start_time: datetime | None
    end_time: datetime | None
    topic_count: int
    message_count: int
    sensor_types: list[SensorFamily]
    topics: list[IndexedTopicSummary]
    default_episode: DefaultEpisodeSummary | None
    visualization_summary: VisualizationSummary | None
    raw_metadata: SourceAssetMetadata


@dataclass(frozen=True)
class SavedConversionConfigSummary:
    id: str
    name: str
    description: str | None
    metadata: dict[str, Any]
    spec_document_version: int
    document_path: str
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime | None
    invalid_reason: str | None


@dataclass(frozen=True)
class SavedConversionConfig:
    id: str
    name: str
    description: str | None
    metadata: dict[str, Any]
    document: ConversionSpecDocument
    spec_document_version: int
    document_path: str
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime | None
    invalid_reason: str | None


@dataclass(frozen=True)
class SavedConversionConfigRevisionSummary:
    id: str
    config_id: str
    revision_number: int
    description: str | None
    metadata: dict[str, Any]
    spec_document_version: int
    document_path: str
    created_at: datetime
    invalid_reason: str | None


@dataclass(frozen=True)
class SavedConversionConfigRevision:
    id: str
    config_id: str
    revision_number: int
    description: str | None
    metadata: dict[str, Any]
    document: ConversionSpecDocument
    spec_document_version: int
    document_path: str
    created_at: datetime
    invalid_reason: str | None


@dataclass(frozen=True)
class ConversionDraftRevisionSummary:
    id: str
    label: str | None
    saved_config_id: str | None
    source_asset_id: str | None
    metadata: dict[str, Any]
    spec_document_version: int
    document_path: str
    created_at: datetime
    invalid_reason: str | None


@dataclass(frozen=True)
class ConversionDraftRevision:
    id: str
    label: str | None
    saved_config_id: str | None
    source_asset_id: str | None
    metadata: dict[str, Any]
    document: ConversionSpecDocument
    spec_document_version: int
    document_path: str
    created_at: datetime
    invalid_reason: str | None


@dataclass(frozen=True)
class WorkspaceJob:
    id: str
    kind: str
    status: str
    target_asset_ids: list[str]
    config: dict[str, Any]
    conversion_run_id: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


@dataclass(frozen=True)
class ConversionRun:
    id: str
    job_id: str | None
    status: str
    source_asset_ids: list[str]
    source_asset_paths: list[str]
    saved_config_id: str | None
    saved_config_revision_id: str | None
    config: dict[str, Any]
    output_dir: str
    output_paths: list[str]
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


@dataclass(frozen=True)
class OutputArtifactSummary:
    id: str
    conversion_run_id: str | None
    source_asset_id: str | None
    source_asset_path: str | None
    output_path: str
    format: str
    role: str
    created_at: datetime
    saved_config_id: str | None
    manifest_available: bool
    report_available: bool


@dataclass(frozen=True)
class OutputArtifact:
    id: str
    conversion_run_id: str | None
    source_asset_id: str | None
    source_asset_path: str | None
    output_path: str
    relative_path: str
    file_name: str
    format: str
    role: str
    size_bytes: int
    availability_status: str
    media_type: str | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    saved_config_id: str | None
    manifest_available: bool
    report_available: bool
