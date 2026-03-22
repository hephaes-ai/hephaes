from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ._converter_helpers import _json_default
from ._utils import compute_path_size_bytes
from ._version import __version__
from .models import (
    OutputConfig,
    ReaderMetadata,
    ResampleConfig,
    RosVersion,
    StorageFormat,
    TemporalMetadata,
)

MANIFEST_VERSION = 1


class ManifestLabels(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auto_tags: list[str] | None = None
    vlm_description: str | None = None
    objects_detected: list[str] | None = None


class ManifestPrivacy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_anonymized: bool = False
    anonymization_method: str | None = None


class DatasetArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    format: Literal["parquet", "tfrecord"]
    file_size_bytes: int = Field(ge=0)
    rows_written: int = Field(ge=0)
    field_names: list[str]
    split_name: str | None = None
    shard_index: int | None = None
    num_shards: int = Field(default=1, ge=1)
    output_filename: str | None = None


class SourceArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    ros_version: RosVersion
    storage_format: StorageFormat
    file_size_bytes: int = Field(ge=0)
    source_metadata: dict[str, Any] | None = None


class ConversionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    output: dict[str, Any]
    row_strategy: dict[str, Any] | None = None
    resample: dict[str, Any] | None = None
    mapping_requested: dict[str, list[str]]
    mapping_resolved: dict[str, str | None]
    schema_spec: dict[str, Any] | None = Field(default=None, alias="schema", serialization_alias="schema")
    features: dict[str, Any] = Field(default_factory=dict)
    labels_spec: dict[str, Any] | None = Field(default=None, alias="labels", serialization_alias="labels")
    draft_origin: dict[str, Any] | None = None
    split: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    preflight: dict[str, Any] | None = None
    rows_written: int | None = None
    dropped_rows: int | None = None
    split_counts: dict[str, int] = Field(default_factory=dict)
    missing_feature_counts: dict[str, int] = Field(default_factory=dict)
    missing_topic_counts: dict[str, int] = Field(default_factory=dict)
    missing_feature_rates: dict[str, float] = Field(default_factory=dict)
    missing_topic_rates: dict[str, float] = Field(default_factory=dict)


class EpisodeManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_version: int = Field(default=MANIFEST_VERSION, ge=1)
    hephaes_version: str = Field(default=__version__, min_length=1)
    episode_id: str = Field(min_length=1)
    dataset: DatasetArtifact
    source: SourceArtifact
    temporal: TemporalMetadata
    conversion: ConversionManifest
    robot_context: dict[str, Any] | None = None
    labels: ManifestLabels = Field(default_factory=ManifestLabels)
    privacy: ManifestPrivacy = Field(default_factory=ManifestPrivacy)


def manifest_path_for_dataset(dataset_path: str | Path) -> Path:
    return Path(dataset_path).with_suffix(".manifest.json")


def build_episode_manifest(
    *,
    episode_id: str,
    dataset_path: str | Path,
    field_names: list[str],
    rows_written: int,
    reader_metadata: ReaderMetadata,
    temporal_metadata: TemporalMetadata,
    output: OutputConfig,
    resample: ResampleConfig | None,
    mapping_requested: dict[str, list[str]],
    mapping_resolved: dict[str, str | None],
    robot_context: dict[str, Any] | None = None,
    schema: dict[str, Any] | None = None,
    features: dict[str, Any] | None = None,
    labels: dict[str, Any] | None = None,
    row_strategy: dict[str, Any] | None = None,
    draft_origin: dict[str, Any] | None = None,
    split: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    preflight: dict[str, Any] | None = None,
    split_name: str | None = None,
    shard_index: int | None = None,
    num_shards: int = 1,
    output_filename: str | None = None,
    dropped_rows: int | None = None,
    split_counts: dict[str, int] | None = None,
    missing_feature_counts: dict[str, int] | None = None,
    missing_topic_counts: dict[str, int] | None = None,
    missing_feature_rates: dict[str, float] | None = None,
    missing_topic_rates: dict[str, float] | None = None,
) -> EpisodeManifest:
    resolved_dataset_path = Path(dataset_path)
    return EpisodeManifest(
        episode_id=episode_id,
        dataset=DatasetArtifact(
            path=str(resolved_dataset_path),
            format=output.format,
            file_size_bytes=compute_path_size_bytes(resolved_dataset_path),
            rows_written=rows_written,
            field_names=list(field_names),
            split_name=split_name,
            shard_index=shard_index,
            num_shards=num_shards,
            output_filename=output_filename,
        ),
        source=SourceArtifact(**reader_metadata.model_dump()),
        temporal=temporal_metadata,
        conversion=ConversionManifest(
            output=output.model_dump(),
            row_strategy=dict(row_strategy or {}) or None,
            resample=resample.model_dump() if resample is not None else None,
            mapping_requested={key: list(value) for key, value in mapping_requested.items()},
            mapping_resolved=dict(mapping_resolved),
            schema_spec=schema,
            features=dict(features or {}),
            labels_spec=dict(labels or {}) or None,
            draft_origin=dict(draft_origin or {}) or None,
            split=split,
            validation=dict(validation or {}) or None,
            preflight=dict(preflight or {}) or None,
            rows_written=rows_written,
            dropped_rows=dropped_rows,
            split_counts=dict(split_counts or {}),
            missing_feature_counts=dict(missing_feature_counts or {}),
            missing_topic_counts=dict(missing_topic_counts or {}),
            missing_feature_rates=dict(missing_feature_rates or {}),
            missing_topic_rates=dict(missing_topic_rates or {}),
        ),
        robot_context=dict(robot_context) if robot_context is not None else None,
    )


def write_episode_manifest(
    manifest: EpisodeManifest,
    *,
    dataset_path: str | Path,
) -> Path:
    path = manifest_path_for_dataset(dataset_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        manifest.model_dump(by_alias=True),
        indent=2,
        default=_json_default,
    )
    path.write_text(payload + "\n", encoding="utf-8")
    return path
