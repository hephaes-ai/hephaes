"""Translate package-owned workspace models into backend API responses."""

from __future__ import annotations

from pathlib import Path

from app.schemas.assets import (
    AssetListItem,
    AssetMetadataResponse,
    AssetSummary,
    DefaultEpisodeSummary,
    IndexedTopicSummary,
    TagCatalogResponse,
    TagResponse,
)
from app.schemas.conversion_authoring import (
    ConversionInspectionRequest,
    SavedConversionConfigDetailResponse,
    SavedConversionDraftRevisionResponse,
    SavedConversionConfigRevisionResponse,
    SavedConversionConfigSummaryResponse,
)
from app.schemas.conversions import (
    ConversionDetailResponse,
    ConversionRepresentationPolicy,
    ConversionSummaryResponse,
)
from app.schemas.jobs import JobResponse
from app.schemas.outputs import OutputArtifactDetailResponse, OutputArtifactSummaryResponse
from hephaes import (
    DraftSpecRequest,
    DraftSpecResult,
    ConversionDraftRevisionSummary,
    ConversionRun,
    IndexedAssetMetadata,
    InspectionResult,
    OutputArtifact,
    OutputArtifactSummary,
    PreviewResult,
    RegisteredAsset,
    ConversionDraftRevision,
    SavedConversionConfig,
    SavedConversionConfigRevision,
    SavedConversionConfigSummary,
    WorkspaceJob,
    WorkspaceTag,
)


def asset_display_path(asset: RegisteredAsset) -> str:
    return asset.file_path


def map_asset_summary(asset: RegisteredAsset) -> AssetSummary:
    return AssetSummary(
        id=asset.id,
        file_path=asset_display_path(asset),
        file_name=asset.file_name,
        file_type=asset.file_type,
        file_size=asset.file_size,
        registered_time=asset.registered_at,
        indexing_status=asset.indexing_status,
        last_indexed_time=asset.last_indexed_at,
    )


def map_asset_list_item(asset: RegisteredAsset, *, tags: list[WorkspaceTag]) -> AssetListItem:
    return AssetListItem(
        **map_asset_summary(asset).model_dump(),
        tags=[map_tag_response(tag) for tag in tags],
    )


def map_tag_response(tag: WorkspaceTag) -> TagResponse:
    return TagResponse(
        id=tag.id,
        name=tag.name,
        created_at=tag.created_at,
    )


def map_tag_catalog_response(tag: WorkspaceTag, *, asset_count: int) -> TagCatalogResponse:
    return TagCatalogResponse(
        id=tag.id,
        name=tag.name,
        created_at=tag.created_at,
        asset_count=asset_count,
    )


def map_asset_metadata(metadata: IndexedAssetMetadata) -> AssetMetadataResponse:
    return AssetMetadataResponse(
        default_episode=(
            DefaultEpisodeSummary(
                duration=metadata.default_episode.duration,
                episode_id=metadata.default_episode.episode_id,
                label=metadata.default_episode.label,
            )
            if metadata.default_episode is not None
            else None
        ),
        duration=metadata.duration,
        end_time=metadata.end_time,
        indexing_error=metadata.indexing_error,
        message_count=metadata.message_count,
        raw_metadata=(
            {
                "compression_format": metadata.raw_metadata.compression_format,
                "file_path": metadata.raw_metadata.file_path,
                "file_size_bytes": metadata.raw_metadata.file_size_bytes,
                "path": metadata.raw_metadata.path,
                "ros_version": metadata.raw_metadata.ros_version,
                "storage_format": metadata.raw_metadata.storage_format,
            }
            if metadata.raw_metadata is not None
            else {}
        ),
        sensor_types=[str(sensor_type) for sensor_type in metadata.sensor_types],
        start_time=metadata.start_time,
        topic_count=metadata.topic_count,
        topics=[
            IndexedTopicSummary(
                message_count=topic.message_count,
                message_type=topic.message_type,
                modality=topic.modality,
                name=topic.name,
                rate_hz=topic.rate_hz,
            )
            for topic in metadata.topics
        ],
    )


def _map_job_type(kind: str) -> str:
    if kind == "index_asset":
        return "index"
    if kind == "conversion":
        return "convert"
    if kind == "prepare_visualization":
        return "prepare_visualization"
    return kind


def _map_job_status(status: str) -> str:
    if status == "pending":
        return "queued"
    return status


def map_job_response(
    job: WorkspaceJob,
    *,
    output_path: str | None = None,
    representation_policy: dict | None = None,
) -> JobResponse:
    config_json = dict(job.config)
    config_json.pop("max_workers", None)
    return JobResponse(
        id=job.id,
        type=_map_job_type(job.kind),
        status=_map_job_status(job.status),
        target_asset_ids_json=list(job.target_asset_ids),
        config_json=config_json,
        representation_policy=representation_policy or config_json.get("representation_policy"),
        output_path=output_path or config_json.get("output_path"),
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        finished_at=job.completed_at,
    )


def _representation_policy_from_config(config: dict) -> ConversionRepresentationPolicy | None:
    policy_payload = config.get("representation_policy")
    if isinstance(policy_payload, dict):
        normalized = dict(policy_payload)
        if (
            "effective_image_payload_contract" in normalized
            and "image_payload_contract" not in normalized
        ):
            normalized["image_payload_contract"] = normalized[
                "effective_image_payload_contract"
            ]
        normalized.pop("effective_image_payload_contract", None)
        return ConversionRepresentationPolicy.model_validate(normalized)
    return None


def map_conversion_summary(run: ConversionRun) -> ConversionSummaryResponse:
    return ConversionSummaryResponse(
        id=run.id,
        job_id=run.job_id or "",
        status=_map_job_status(run.status),
        asset_ids=list(run.source_asset_ids),
        config=dict(run.config),
        output_path=run.output_dir,
        error_message=run.error_message,
        representation_policy=_representation_policy_from_config(run.config),
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def map_conversion_detail(run: ConversionRun, *, job: WorkspaceJob | None = None) -> ConversionDetailResponse:
    summary = map_conversion_summary(run)
    return ConversionDetailResponse(
        **summary.model_dump(),
        output_files=list(run.output_paths),
        job=map_job_response(
            job or WorkspaceJob(
                id=run.job_id or "",
                kind="conversion",
                status=run.status,
                target_asset_ids=list(run.source_asset_ids),
                config=dict(run.config),
                conversion_run_id=run.id,
                error_message=run.error_message,
                created_at=run.created_at,
                updated_at=run.updated_at,
                started_at=run.started_at,
                completed_at=run.completed_at,
            ),
            output_path=run.output_dir,
        ),
    )


def map_saved_conversion_config_summary(
    config: SavedConversionConfigSummary,
    *,
    revision_count: int,
    draft_count: int,
    migration_notes: list[str] | None = None,
    resolved_config: SavedConversionConfig | None = None,
    latest_preview_available: bool = False,
    latest_preview_updated_at=None,
) -> SavedConversionConfigSummaryResponse:
    response = SavedConversionConfigSummaryResponse(
        id=config.id,
        name=config.name,
        description=config.description,
        metadata=dict(config.metadata),
        spec_document_version=config.spec_document_version,
        spec_schema_name=None,
        spec_schema_version=None,
        spec_row_strategy_kind=None,
        spec_output_format=None,
        spec_output_compression=None,
        spec_feature_count=0,
        revision_count=revision_count,
        draft_count=draft_count,
        migration_notes=list(migration_notes or []),
        invalid_reason=config.invalid_reason,
        latest_preview_available=latest_preview_available,
        latest_preview_updated_at=latest_preview_updated_at,
        created_at=config.created_at,
        updated_at=config.updated_at,
        last_opened_at=config.last_opened_at,
        status="invalid" if config.invalid_reason else "ready",
    )
    if resolved_config is not None:
        return _apply_config_document_fields(response, resolved_config)
    return response


def _apply_config_document_fields(
    response: SavedConversionConfigSummaryResponse,
    config: SavedConversionConfig,
) -> SavedConversionConfigSummaryResponse:
    spec = config.document.spec
    return response.model_copy(
        update={
            "spec_schema_name": spec.schema.name,
            "spec_schema_version": spec.schema.version,
            "spec_row_strategy_kind": spec.row_strategy.kind if spec.row_strategy is not None else None,
            "spec_output_format": spec.output.format,
            "spec_output_compression": spec.output.compression,
            "spec_feature_count": len(spec.features),
        }
    )


def _map_config_revision_kind(revision: SavedConversionConfigRevision, *, total_count: int) -> str:
    if revision.revision_number == 1:
        return "create"
    if revision.description is not None and "migrat" in revision.description.casefold():
        return "migration"
    if revision.revision_number == total_count:
        return "update"
    return "update"


def _collect_config_migration_notes(revisions: list[SavedConversionConfigRevision]) -> list[str]:
    notes: list[str] = []
    for revision in revisions:
        description = revision.description
        if description is None or "migrat" not in description.casefold():
            continue
        if description not in notes:
            notes.append(description)
    return notes


def map_saved_conversion_config_detail(
    config: SavedConversionConfig,
    *,
    revisions: list[SavedConversionConfigRevision],
    draft_revisions: list[ConversionDraftRevision],
) -> SavedConversionConfigDetailResponse:
    latest_preview_revision = next(
        (draft_revision for draft_revision in draft_revisions if draft_revision.preview_json is not None),
        None,
    )
    summary = _apply_config_document_fields(
        map_saved_conversion_config_summary(
            config,
            revision_count=len(revisions),
            draft_count=len(draft_revisions),
            migration_notes=_collect_config_migration_notes(revisions),
            resolved_config=config,
            latest_preview_available=latest_preview_revision is not None,
            latest_preview_updated_at=(
                latest_preview_revision.updated_at if latest_preview_revision is not None else None
            ),
        ),
        config,
    )
    return SavedConversionConfigDetailResponse(
        **summary.model_dump(),
        spec_document_json=config.document.model_dump(mode="json", by_alias=True),
        resolved_spec=config.document.spec,
        resolved_spec_document=config.document,
        latest_preview=(
            PreviewResult.model_validate(latest_preview_revision.preview_json)
            if latest_preview_revision is not None and latest_preview_revision.preview_json is not None
            else None
        ),
        revisions=[
            SavedConversionConfigRevisionResponse(
                id=revision.id,
                config_id=revision.config_id,
                revision_number=revision.revision_number,
                change_kind=_map_config_revision_kind(revision, total_count=len(revisions)),
                change_summary=revision.description,
                spec_document_version=revision.spec_document_version,
                spec_document_json=revision.document.model_dump(mode="json", by_alias=True),
                resolved_spec=revision.document.spec,
                created_at=revision.created_at,
            )
            for revision in revisions
        ],
        draft_revisions=[
            SavedConversionDraftRevisionResponse(
                id=draft_revision.id,
                saved_config_id=draft_revision.saved_config_id,
                revision_number=draft_revision.revision_number,
                source_asset_id=draft_revision.source_asset_id,
                status=draft_revision.status,
                inspection_request=ConversionInspectionRequest.model_validate(
                    draft_revision.inspection_request_json
                ),
                inspection=InspectionResult.model_validate(draft_revision.inspection_json),
                draft_request=DraftSpecRequest.model_validate(draft_revision.draft_request_json),
                draft_result=DraftSpecResult.model_validate(draft_revision.draft_result_json),
                preview=(
                    PreviewResult.model_validate(draft_revision.preview_json)
                    if draft_revision.preview_json is not None
                    else None
                ),
                created_at=draft_revision.created_at,
                updated_at=draft_revision.updated_at,
            )
            for draft_revision in draft_revisions
        ],
    )


def map_output_summary(
    artifact: OutputArtifactSummary,
    *,
    job_id: str | None = None,
    asset_ids: list[str] | None = None,
) -> OutputArtifactSummaryResponse:
    conversion_id = artifact.conversion_run_id or ""
    resolved_job_id = job_id or conversion_id
    content_url = f"/outputs/{artifact.id}/content"
    relative_path = (
        str(Path(artifact.output_path).name)
        if Path(artifact.output_path).name
        else artifact.output_path
    )
    return OutputArtifactSummaryResponse(
        id=artifact.id,
        conversion_id=conversion_id,
        job_id=resolved_job_id,
        asset_ids=(
            list(asset_ids)
            if asset_ids is not None
            else ([artifact.source_asset_id] if artifact.source_asset_id is not None else [])
        ),
        relative_path=relative_path,
        file_name=Path(artifact.output_path).name,
        format=artifact.format,
        role=artifact.role,
        media_type=None,
        size_bytes=0,
        availability_status="ready",
        metadata={},
        content_url=content_url,
        created_at=artifact.created_at,
        updated_at=artifact.created_at,
    )


def map_output_detail(
    artifact: OutputArtifact,
    *,
    job_id: str | None = None,
    asset_ids: list[str] | None = None,
) -> OutputArtifactDetailResponse:
    summary = map_output_summary(
        OutputArtifactSummary(
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
        ),
        job_id=job_id,
        asset_ids=asset_ids,
    )
    payload = summary.model_dump()
    payload.update(
        {
            "media_type": artifact.media_type,
            "size_bytes": artifact.size_bytes,
            "availability_status": artifact.availability_status,
            "metadata": dict(artifact.metadata),
            "file_path": artifact.output_path,
            "updated_at": artifact.updated_at,
        }
    )
    return OutputArtifactDetailResponse.model_validate(payload)
