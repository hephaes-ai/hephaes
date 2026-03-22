"""Pydantic schemas for conversion authoring, reusable configs, and drafts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hephaes import build_conversion_capabilities
from hephaes.conversion import ConversionCapabilities
from hephaes.conversion.draft_spec import DraftSpecRequest, DraftSpecResult
from hephaes.conversion.introspection import InspectionResult
from hephaes.conversion.preview import PreviewResult
from hephaes.conversion.spec_io import CONVERSION_SPEC_DOCUMENT_VERSION, ConversionSpecDocument
from hephaes.models import ConversionSpec, DecodeFailurePolicy

AuthoringPersistenceMode = Literal["sqlite-json"]
SavedConversionConfigStatus = Literal["ready", "needs_migration", "invalid"]
SavedConversionConfigRevisionKind = Literal["create", "update", "duplicate", "migration", "import"]
SavedConversionDraftStatus = Literal["draft", "saved", "discarded"]


def _normalize_non_empty_string(value: object) -> object:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        raise ValueError("value must be non-empty")
    return stripped


def _normalize_optional_string(value: object) -> object:
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return None
    return stripped


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _normalize_string_list(value: object) -> object:
    if not isinstance(value, list):
        return value
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise TypeError("values must be strings")
        stripped = item.strip()
        if not stripped:
            raise ValueError("values must be non-empty")
        normalized.append(stripped)
    return list(dict.fromkeys(normalized))


class ConversionInspectionOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topics: list[str] = Field(default_factory=list)
    sample_n: int = Field(default=8, ge=1)
    max_depth: int = Field(default=4, ge=0)
    max_sequence_items: int = Field(default=4, ge=1)
    on_failure: DecodeFailurePolicy = "warn"
    topic_type_hints: dict[str, str] = Field(default_factory=dict)

    @field_validator("topics", mode="before")
    @classmethod
    def normalize_topics(cls, value: object) -> object:
        return _normalize_string_list(value)

    @field_validator("topic_type_hints", mode="before")
    @classmethod
    def normalize_topic_type_hints(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized: dict[str, str] = {}
        for key, hint in value.items():
            if not isinstance(key, str) or not isinstance(hint, str):
                raise TypeError("topic_type_hints must map strings to strings")
            stripped_key = key.strip()
            stripped_hint = hint.strip()
            if not stripped_key or not stripped_hint:
                raise ValueError("topic_type_hints entries must be non-empty")
            normalized[stripped_key] = stripped_hint
        return normalized


class ConversionInspectionRequest(ConversionInspectionOptions):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)

    @field_validator("asset_id")
    @classmethod
    def normalize_asset_id(cls, value: str) -> str:
        return _normalize_non_empty_string(value)  # type: ignore[return-value]


class ConversionInspectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    request: ConversionInspectionRequest
    inspection: InspectionResult

    @field_validator("asset_id")
    @classmethod
    def normalize_asset_id(cls, value: str) -> str:
        return _normalize_non_empty_string(value)  # type: ignore[return-value]


class ConversionDraftRequest(ConversionInspectionOptions):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    draft_request: DraftSpecRequest = Field(default_factory=DraftSpecRequest)

    @field_validator("asset_id")
    @classmethod
    def normalize_asset_id(cls, value: str) -> str:
        return _normalize_non_empty_string(value)  # type: ignore[return-value]


class ConversionDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    request: ConversionDraftRequest
    inspection: InspectionResult
    draft: DraftSpecResult
    draft_revision_id: str | None = None

    @field_validator("asset_id")
    @classmethod
    def normalize_asset_id(cls, value: str) -> str:
        return _normalize_non_empty_string(value)  # type: ignore[return-value]


class ConversionPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    spec: ConversionSpec
    sample_n: int = Field(default=5, ge=1)
    topic_type_hints: dict[str, str] = Field(default_factory=dict)

    @field_validator("asset_id")
    @classmethod
    def normalize_asset_id(cls, value: str) -> str:
        return _normalize_non_empty_string(value)  # type: ignore[return-value]

    @field_validator("topic_type_hints", mode="before")
    @classmethod
    def normalize_topic_type_hints(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized: dict[str, str] = {}
        for key, hint in value.items():
            if not isinstance(key, str) or not isinstance(hint, str):
                raise TypeError("topic_type_hints must map strings to strings")
            stripped_key = key.strip()
            stripped_hint = hint.strip()
            if not stripped_key or not stripped_hint:
                raise ValueError("topic_type_hints entries must be non-empty")
            normalized[stripped_key] = stripped_hint
        return normalized


class ConversionPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    request: ConversionPreviewRequest
    preview: PreviewResult

    @field_validator("asset_id")
    @classmethod
    def normalize_asset_id(cls, value: str) -> str:
        return _normalize_non_empty_string(value)  # type: ignore[return-value]


class ConversionAuthoringPersistenceCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: AuthoringPersistenceMode = "sqlite-json"
    supports_saved_configs: bool = True
    supports_saved_config_revisions: bool = True
    supports_draft_revisions: bool = True
    supports_preview_snapshots: bool = True
    supports_migration_on_load: bool = True
    supports_execute_from_saved_config: bool = True
    spec_document_version: int = Field(default=CONVERSION_SPEC_DOCUMENT_VERSION, ge=1)


class ConversionAuthoringCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authoring_api_version: int = Field(default=1, ge=1)
    hephaes: ConversionCapabilities = Field(default_factory=build_conversion_capabilities)
    persistence: ConversionAuthoringPersistenceCapabilities = Field(
        default_factory=ConversionAuthoringPersistenceCapabilities
    )


class SavedConversionConfigCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    spec: ConversionSpec

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _normalize_non_empty_string(value)  # type: ignore[return-value]

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return _normalize_optional_string(value)  # type: ignore[return-value]


class SavedConversionConfigUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None
    spec: ConversionSpec | None = None

    @field_validator("name", "description", mode="before")
    @classmethod
    def normalize_strings(cls, value: object) -> object:
        return _normalize_optional_string(value)

    @model_validator(mode="after")
    def validate_update_payload(self) -> "SavedConversionConfigUpdateRequest":
        if all(value is None for value in (self.name, self.description, self.metadata, self.spec)):
            raise ValueError("update payload must include at least one field")
        return self


class SavedConversionConfigDuplicateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("name", "description", mode="before")
    @classmethod
    def normalize_strings(cls, value: object) -> object:
        return _normalize_optional_string(value)


class SavedConversionConfigRevisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    config_id: str = Field(min_length=1)
    revision_number: int = Field(ge=1)
    change_kind: SavedConversionConfigRevisionKind
    change_summary: str | None = None
    spec_document_version: int = Field(ge=1)
    spec_document_json: dict[str, Any] = Field(default_factory=dict)
    resolved_spec: ConversionSpec | None = None
    created_at: datetime

    @field_validator("id", "config_id")
    @classmethod
    def normalize_ids(cls, value: str) -> str:
        return _normalize_non_empty_string(value)  # type: ignore[return-value]

    @field_validator("change_summary")
    @classmethod
    def normalize_change_summary(cls, value: str | None) -> str | None:
        return _normalize_optional_string(value)  # type: ignore[return-value]

    @field_validator("created_at", mode="before")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        normalized = _normalize_datetime(value)
        assert normalized is not None
        return normalized


class SavedConversionDraftRevisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    saved_config_id: str | None = None
    revision_number: int = Field(ge=1)
    source_asset_id: str | None = None
    status: SavedConversionDraftStatus
    inspection_request: ConversionInspectionRequest
    inspection: InspectionResult
    draft_request: DraftSpecRequest
    draft_result: DraftSpecResult
    preview: PreviewResult | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("id", "saved_config_id", "source_asset_id")
    @classmethod
    def normalize_optional_ids(cls, value: str | None) -> str | None:
        return _normalize_optional_string(value)  # type: ignore[return-value]

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def normalize_datetimes(cls, value: datetime | None) -> datetime | None:
        return _normalize_datetime(value)


class SavedConversionConfigSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    spec_document_version: int = Field(ge=1)
    spec_schema_name: str | None = None
    spec_schema_version: int | None = None
    spec_row_strategy_kind: str | None = None
    spec_output_format: str | None = None
    spec_output_compression: str | None = None
    spec_feature_count: int = Field(default=0, ge=0)
    revision_count: int = Field(default=0, ge=0)
    draft_count: int = Field(default=0, ge=0)
    migration_notes: list[str] = Field(default_factory=list)
    invalid_reason: str | None = None
    latest_preview_available: bool = False
    latest_preview_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime | None = None
    status: SavedConversionConfigStatus = "ready"

    @field_validator("id", "name")
    @classmethod
    def normalize_ids_and_name(cls, value: str) -> str:
        return _normalize_non_empty_string(value)  # type: ignore[return-value]

    @field_validator("description", "invalid_reason")
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        return _normalize_optional_string(value)  # type: ignore[return-value]

    @field_validator("migration_notes", mode="before")
    @classmethod
    def normalize_migration_notes(cls, value: object) -> object:
        return _normalize_string_list(value)

    @field_validator("created_at", "updated_at", "last_opened_at", "latest_preview_updated_at", mode="before")
    @classmethod
    def normalize_datetimes(cls, value: datetime | None) -> datetime | None:
        return _normalize_datetime(value)


class SavedConversionConfigDetailResponse(SavedConversionConfigSummaryResponse):
    model_config = ConfigDict(extra="forbid")

    spec_document_json: dict[str, Any] = Field(default_factory=dict)
    resolved_spec: ConversionSpec | None = None
    resolved_spec_document: ConversionSpecDocument | None = None
    latest_preview: PreviewResult | None = None
    revisions: list[SavedConversionConfigRevisionResponse] = Field(default_factory=list)
    draft_revisions: list[SavedConversionDraftRevisionResponse] = Field(default_factory=list)


class SavedConversionConfigListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SavedConversionConfigSummaryResponse] = Field(default_factory=list)
    total_count: int = Field(default=0, ge=0)
