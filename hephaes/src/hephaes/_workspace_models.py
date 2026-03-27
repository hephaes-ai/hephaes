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
    outputs_dir: Path
    specs_dir: Path
    jobs_dir: Path


@dataclass(frozen=True)
class RegisteredAsset:
    id: str
    file_path: str
    file_name: str
    file_type: str
    file_size: int
    registered_at: datetime
    updated_at: datetime
    indexing_status: str
    last_indexed_at: datetime | None


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
