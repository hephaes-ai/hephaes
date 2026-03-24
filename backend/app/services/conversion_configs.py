"""Service helpers for saved conversion config persistence and migration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    ConversionConfig,
    ConversionConfigRevision,
    ConversionDraftRevision,
    utc_now,
)
from app.schemas.conversion_authoring import (
    ConversionDraftRequest,
    ConversionInspectionRequest,
    SavedConversionConfigCreateRequest,
    SavedConversionConfigDetailResponse,
    SavedConversionConfigDuplicateRequest,
    SavedConversionConfigRevisionResponse,
    SavedConversionConfigStatus,
    SavedConversionConfigSummaryResponse,
    SavedConversionConfigUpdateRequest,
    SavedConversionDraftRevisionResponse,
    SavedConversionDraftStatus,
)
from hephaes._converter_helpers import _normalize_payload
from hephaes.conversion.draft_spec import DraftSpecRequest, DraftSpecResult
from hephaes.conversion.introspection import InspectionResult
from hephaes.conversion.preview import PreviewResult
from hephaes.conversion.spec_io import (
    CONVERSION_SPEC_DOCUMENT_VERSION,
    ConversionSpecDocument,
    build_conversion_spec_document,
    load_conversion_spec_document,
    migrate_conversion_spec_document,
)


class ConversionConfigServiceError(Exception):
    """Base exception for reusable config workflow failures."""


class ConversionConfigNotFoundError(ConversionConfigServiceError):
    """Raised when a requested saved config cannot be found."""


class ConversionConfigValidationError(ConversionConfigServiceError):
    """Raised when a saved config write request is invalid or conflicts."""


class ConversionConfigInvalidError(ConversionConfigServiceError):
    """Raised when a saved config document cannot be loaded or migrated."""


@dataclass(frozen=True)
class _ResolvedConfigDocument:
    document: ConversionSpecDocument | None
    needs_migration: bool
    invalid_reason: str | None


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _model_dump_json_safe(model: Any) -> dict[str, Any]:
    """Dump pydantic models while preserving binary payloads as JSON-safe dicts."""

    payload = model.model_dump(mode="python", by_alias=True)
    normalized = _normalize_payload(payload)
    if not isinstance(normalized, dict):  # pragma: no cover - defensive guard
        raise TypeError("expected model dump to produce a dictionary payload")
    return normalized


def _document_summary(document: ConversionSpecDocument | None) -> dict[str, Any]:
    if document is None:
        return {
            "spec_schema_name": None,
            "spec_schema_version": None,
            "spec_row_strategy_kind": None,
            "spec_output_format": None,
            "spec_output_compression": None,
            "spec_feature_count": 0,
        }

    spec = document.spec
    return {
        "spec_schema_name": spec.schema.name,
        "spec_schema_version": spec.schema.version,
        "spec_row_strategy_kind": spec.row_strategy.kind if spec.row_strategy is not None else None,
        "spec_output_format": spec.output.format,
        "spec_output_compression": spec.output.compression,
        "spec_feature_count": len(spec.features),
    }


def _build_revision_response(
    revision: ConversionConfigRevision,
) -> SavedConversionConfigRevisionResponse:
    spec_document = dict(revision.spec_document_json)
    try:
        resolved_spec = load_conversion_spec_document(spec_document)
    except Exception:
        resolved_spec = None
    return SavedConversionConfigRevisionResponse(
        id=revision.id,
        config_id=revision.config_id,
        revision_number=revision.revision_number,
        change_kind=revision.change_kind,  # type: ignore[arg-type]
        change_summary=revision.change_summary,
        spec_document_version=revision.spec_document_version,
        spec_document_json=spec_document,
        resolved_spec=resolved_spec.spec if resolved_spec is not None else None,
        created_at=revision.created_at,
    )


def _build_draft_revision_response(
    draft_revision: ConversionDraftRevision,
) -> SavedConversionDraftRevisionResponse:
    inspection_request = ConversionInspectionRequest.model_validate(draft_revision.inspection_request_json)
    inspection = InspectionResult.model_validate(draft_revision.inspection_json)
    draft_request = DraftSpecRequest.model_validate(draft_revision.draft_request_json)
    draft_result = DraftSpecResult.model_validate(draft_revision.draft_result_json)
    preview = (
        PreviewResult.model_validate(draft_revision.preview_json)
        if draft_revision.preview_json is not None
        else None
    )

    return SavedConversionDraftRevisionResponse(
        id=draft_revision.id,
        saved_config_id=draft_revision.saved_config_id,
        revision_number=draft_revision.revision_number,
        source_asset_id=draft_revision.source_asset_id,
        status=draft_revision.status,  # type: ignore[arg-type]
        inspection_request=inspection_request,
        inspection=inspection,
        draft_request=draft_request,
        draft_result=draft_result,
        preview=preview,
        created_at=draft_revision.created_at,
        updated_at=draft_revision.updated_at,
    )


def _build_summary_response(
    config: ConversionConfig,
    *,
    resolved: _ResolvedConfigDocument,
) -> SavedConversionConfigSummaryResponse:
    summary_fields = _document_summary(resolved.document)
    migration_notes = list(config.migration_notes_json)
    if resolved.needs_migration:
        migration_note = (
            "conversion spec document version "
            f"{config.spec_document_version} will migrate to {CONVERSION_SPEC_DOCUMENT_VERSION}"
        )
        if migration_note not in migration_notes:
            migration_notes.append(migration_note)

    status: SavedConversionConfigStatus
    if resolved.invalid_reason is not None or config.invalid_reason is not None:
        status = "invalid"
    elif resolved.needs_migration:
        status = "needs_migration"
    else:
        status = "ready"

    return SavedConversionConfigSummaryResponse(
        id=config.id,
        name=config.name,
        description=config.description,
        metadata=dict(config.metadata_json),
        spec_document_version=config.spec_document_version,
        migration_notes=migration_notes,
        invalid_reason=resolved.invalid_reason or config.invalid_reason,
        latest_preview_available=config.latest_preview_json is not None,
        latest_preview_updated_at=config.latest_preview_at,
        created_at=config.created_at,
        updated_at=config.updated_at,
        last_opened_at=config.last_opened_at,
        status=status,
        revision_count=len(config.revisions),
        draft_count=len(config.draft_revisions),
        **summary_fields,
    )


class ConversionConfigService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _config_query(self):
        return (
            select(ConversionConfig)
            .options(
                selectinload(ConversionConfig.revisions),
                selectinload(ConversionConfig.draft_revisions),
            )
            .execution_options(populate_existing=True)
            .order_by(ConversionConfig.updated_at.desc(), ConversionConfig.id.desc())
        )

    def _get_config_or_raise(self, config_id: str) -> ConversionConfig:
        statement = self._config_query().where(ConversionConfig.id == config_id)
        config = self.session.scalar(statement)
        if config is None:
            raise ConversionConfigNotFoundError(f"conversion config not found: {config_id}")
        return config

    def _config_name_exists(self, normalized_name: str, *, exclude_config_id: str | None = None) -> bool:
        statement = select(func.count()).select_from(ConversionConfig).where(
            ConversionConfig.normalized_name == normalized_name
        )
        if exclude_config_id is not None:
            statement = statement.where(ConversionConfig.id != exclude_config_id)
        return bool(self.session.scalar(statement))

    def _ensure_unique_name(self, name: str, *, exclude_config_id: str | None = None) -> str:
        normalized_name = _normalize_name(name)
        if self._config_name_exists(normalized_name, exclude_config_id=exclude_config_id):
            raise ConversionConfigValidationError(f"saved config name already exists: {name}")
        return normalized_name

    def _resolve_document(
        self,
        config: ConversionConfig,
        *,
        persist_migration: bool,
        mark_opened: bool,
    ) -> _ResolvedConfigDocument:
        invalid_reason = _normalize_optional_text(config.invalid_reason)
        raw_document = dict(config.spec_document_json)

        try:
            document = load_conversion_spec_document(raw_document)
        except Exception as exc:
            invalid_reason = str(exc)
            if persist_migration:
                config.invalid_reason = invalid_reason
                if mark_opened:
                    config.last_opened_at = utc_now()
                config.updated_at = utc_now()
                self.session.commit()
            return _ResolvedConfigDocument(document=None, needs_migration=False, invalid_reason=invalid_reason)

        needs_migration = document.spec_version < CONVERSION_SPEC_DOCUMENT_VERSION
        if needs_migration:
            migrated_document = migrate_conversion_spec_document(document)
            document = migrated_document
            if persist_migration:
                previous_version = config.spec_document_version
                config.spec_document_json = document.model_dump(mode="json", by_alias=True)
                config.spec_document_version = document.spec_version
                config.invalid_reason = None
                if mark_opened:
                    config.last_opened_at = utc_now()
                config.updated_at = utc_now()
                note = (
                    f"migrated saved config from spec document version {previous_version} "
                    f"to {document.spec_version}"
                )
                notes = list(config.migration_notes_json)
                if note not in notes:
                    notes.append(note)
                config.migration_notes_json = notes
                revision_number = config.current_revision_number + 1
                config.current_revision_number = revision_number
                self.session.add(
                    ConversionConfigRevision(
                        config_id=config.id,
                        revision_number=revision_number,
                        change_kind="migration",
                        change_summary=note,
                        spec_document_json=document.model_dump(mode="json", by_alias=True),
                        spec_document_version=document.spec_version,
                    )
                )
                self.session.commit()
            return _ResolvedConfigDocument(
                document=document,
                needs_migration=not persist_migration,
                invalid_reason=None,
            )

        if persist_migration:
            config.invalid_reason = None
            if mark_opened:
                config.last_opened_at = utc_now()
            config.updated_at = utc_now()
            self.session.commit()
        return _ResolvedConfigDocument(document=document, needs_migration=False, invalid_reason=None)

    def _load_related_config(self, config_id: str) -> ConversionConfig:
        return self._get_config_or_raise(config_id)

    def list_saved_configs(self) -> list[SavedConversionConfigSummaryResponse]:
        configs = list(self.session.scalars(self._config_query()).all())
        summaries: list[SavedConversionConfigSummaryResponse] = []
        for config in configs:
            resolved = self._resolve_document(config, persist_migration=False, mark_opened=False)
            summaries.append(_build_summary_response(config, resolved=resolved))
        return summaries

    def get_saved_config(
        self,
        config_id: str,
        *,
        persist_migration: bool = True,
        mark_opened: bool = True,
    ) -> SavedConversionConfigDetailResponse:
        config = self._load_related_config(config_id)
        resolved = self._resolve_document(
            config,
            persist_migration=persist_migration,
            mark_opened=mark_opened,
        )
        if persist_migration or mark_opened:
            config = self._load_related_config(config_id)

        latest_preview = (
            PreviewResult.model_validate(config.latest_preview_json)
            if config.latest_preview_json is not None
            else None
        )

        return SavedConversionConfigDetailResponse(
            **_build_summary_response(config, resolved=resolved).model_dump(),
            spec_document_json=dict(config.spec_document_json),
            resolved_spec=resolved.document.spec if resolved.document is not None else None,
            resolved_spec_document=resolved.document,
            latest_preview=latest_preview,
            revisions=[
                _build_revision_response(revision)
                for revision in config.revisions
            ],
            draft_revisions=[
                _build_draft_revision_response(draft_revision)
                for draft_revision in config.draft_revisions
            ],
        )

    def _create_config_from_document(
        self,
        *,
        name: str,
        metadata: dict[str, Any],
        description: str | None,
        document: ConversionSpecDocument,
        change_kind: str,
        change_summary: str,
    ) -> ConversionConfig:
        normalized_name = self._ensure_unique_name(name)
        config = ConversionConfig(
            name=name.strip(),
            normalized_name=normalized_name,
            description=_normalize_optional_text(description),
            metadata_json=dict(metadata),
            spec_document_json=document.model_dump(mode="json", by_alias=True),
            spec_document_version=document.spec_version,
            current_revision_number=1,
            latest_preview_json=None,
            latest_preview_at=None,
            invalid_reason=None,
            migration_notes_json=[],
            created_at=utc_now(),
            updated_at=utc_now(),
            last_opened_at=utc_now(),
        )
        self.session.add(config)
        self.session.flush()
        self.session.add(
            ConversionConfigRevision(
                config_id=config.id,
                revision_number=1,
                change_kind=change_kind,
                change_summary=change_summary,
                spec_document_json=document.model_dump(mode="json", by_alias=True),
                spec_document_version=document.spec_version,
            )
        )
        self.session.commit()
        return config

    def create_saved_config(
        self,
        request: SavedConversionConfigCreateRequest,
    ) -> SavedConversionConfigDetailResponse:
        document = build_conversion_spec_document(request.spec, metadata=request.metadata)
        config = self._create_config_from_document(
            name=request.name,
            metadata=request.metadata,
            description=request.description,
            document=document,
            change_kind="create",
            change_summary="created saved config",
        )
        return self.get_saved_config(config.id, persist_migration=False, mark_opened=False)

    def update_saved_config(
        self,
        config_id: str,
        request: SavedConversionConfigUpdateRequest,
    ) -> SavedConversionConfigDetailResponse:
        config = self._get_config_or_raise(config_id)
        resolved = self._resolve_document(
            config,
            persist_migration=True,
            mark_opened=False,
        )
        if resolved.invalid_reason is not None:
            raise ConversionConfigInvalidError(resolved.invalid_reason)
        document = resolved.document
        assert document is not None

        if request.spec is not None:
            metadata = config.metadata_json if request.metadata is None else request.metadata
            document = build_conversion_spec_document(request.spec, metadata=metadata)
            config.spec_document_json = document.model_dump(mode="json", by_alias=True)
            config.spec_document_version = document.spec_version
            config.metadata_json = dict(metadata)
        elif request.metadata is not None:
            config.metadata_json = dict(request.metadata)
            document = build_conversion_spec_document(document.spec, metadata=request.metadata)
            config.spec_document_json = document.model_dump(mode="json", by_alias=True)

        if request.name is not None:
            config.name = request.name.strip()
            config.normalized_name = self._ensure_unique_name(
                config.name,
                exclude_config_id=config.id,
            )
        if request.description is not None:
            config.description = _normalize_optional_text(request.description)

        config.current_revision_number += 1
        config.invalid_reason = None
        config.latest_preview_json = None
        config.latest_preview_at = None
        config.migration_notes_json = []
        config.last_opened_at = utc_now()
        config.updated_at = utc_now()
        self.session.add(
            ConversionConfigRevision(
                config_id=config.id,
                revision_number=config.current_revision_number,
                change_kind="update",
                change_summary="updated saved config",
                spec_document_json=document.model_dump(mode="json", by_alias=True),
                spec_document_version=document.spec_version,
            )
        )
        self.session.commit()
        return self.get_saved_config(config.id, persist_migration=False, mark_opened=False)

    def duplicate_saved_config(
        self,
        config_id: str,
        request: SavedConversionConfigDuplicateRequest,
    ) -> SavedConversionConfigDetailResponse:
        source_config = self._get_config_or_raise(config_id)
        resolved = self._resolve_document(
            source_config,
            persist_migration=True,
            mark_opened=False,
        )
        if resolved.invalid_reason is not None or resolved.document is None:
            raise ConversionConfigInvalidError(resolved.invalid_reason or "saved config is invalid")

        name = request.name or f"Copy of {source_config.name}"
        description = request.description if request.description is not None else source_config.description
        metadata = request.metadata if request.metadata is not None else source_config.metadata_json
        unique_name = name
        suffix = 2
        while self._config_name_exists(_normalize_name(unique_name)):
            unique_name = f"{name} ({suffix})"
            suffix += 1

        config = self._create_config_from_document(
            name=unique_name,
            metadata=dict(metadata),
            description=description,
            document=resolved.document,
            change_kind="duplicate",
            change_summary=f"duplicated from saved config {source_config.id}",
        )
        return self.get_saved_config(config.id, persist_migration=False, mark_opened=False)

    def resolve_saved_config_spec_document(
        self,
        config_id: str,
        *,
        persist_migration: bool = True,
        mark_opened: bool = False,
    ) -> ConversionSpecDocument:
        config = self._get_config_or_raise(config_id)
        resolved = self._resolve_document(
            config,
            persist_migration=persist_migration,
            mark_opened=mark_opened,
        )
        if resolved.invalid_reason is not None or resolved.document is None:
            raise ConversionConfigInvalidError(
                resolved.invalid_reason or f"saved config is invalid: {config_id}"
            )
        return resolved.document

    def record_draft_revision(
        self,
        *,
        saved_config_id: str | None,
        source_asset_id: str | None,
        inspection_request: ConversionInspectionRequest,
        inspection: InspectionResult,
        draft_request: ConversionDraftRequest,
        draft_result: DraftSpecResult,
        preview: PreviewResult | None = None,
    ) -> SavedConversionDraftRevisionResponse:
        if saved_config_id is not None:
            saved_config = self._get_config_or_raise(saved_config_id)
            revision_count_statement = select(func.count()).select_from(ConversionDraftRevision).where(
                ConversionDraftRevision.saved_config_id == saved_config_id
            )
            revision_number = int(self.session.scalar(revision_count_statement) or 0) + 1
            status: SavedConversionDraftStatus = "saved"
        else:
            saved_config = None
            revision_number = 1
            status = "draft"

        preview_result = preview if preview is not None else draft_result.preview
        draft_result_json = _model_dump_json_safe(draft_result)
        preview_json = _model_dump_json_safe(preview_result) if preview_result is not None else None
        draft_row = ConversionDraftRevision(
            saved_config_id=saved_config_id,
            revision_number=revision_number,
            source_asset_id=source_asset_id,
            status=status,
            inspection_request_json=inspection_request.model_dump(mode="json", by_alias=True),
            inspection_json=inspection.model_dump(mode="json", by_alias=True),
            draft_request_json=draft_request.draft_request.model_dump(mode="json", by_alias=True),
            draft_result_json=draft_result_json,
            spec_document_json=draft_result.spec.model_dump(mode="json", by_alias=True),
            spec_document_version=CONVERSION_SPEC_DOCUMENT_VERSION,
            preview_json=preview_json,
            warning_messages_json=list(draft_result.warnings),
            assumption_messages_json=list(draft_result.assumptions),
            unresolved_fields_json=list(draft_result.unresolved_fields),
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.session.add(draft_row)

        if saved_config is not None and preview_result is not None:
            saved_config.latest_preview_json = preview_json
            saved_config.latest_preview_at = utc_now()
            saved_config.updated_at = utc_now()
        self.session.commit()

        return _build_draft_revision_response(draft_row)
