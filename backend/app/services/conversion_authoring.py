"""Service helpers for conversion authoring and reusable config workflows."""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.schemas.conversion_authoring import (
    ConversionAuthoringCapabilitiesResponse,
    ConversionDraftRequest,
    ConversionInspectionRequest,
    ConversionPreviewRequest,
)
from app.services.episodes import open_asset_reader
from hephaes import AssetNotFoundError, Workspace, build_conversion_capabilities
from hephaes.conversion import (
    build_draft_conversion_spec,
    inspect_reader,
    preview_conversion_spec,
)
from hephaes.conversion.introspection import InspectionResult
from hephaes.conversion.draft_spec import DraftSpecResult
from hephaes.conversion.preview import PreviewResult


class ConversionAuthoringServiceError(Exception):
    """Base exception for conversion authoring workflow failures."""


class ConversionAuthoringNotFoundError(ConversionAuthoringServiceError):
    """Raised when an authoring target cannot be found."""


class ConversionAuthoringValidationError(ConversionAuthoringServiceError):
    """Raised when authoring inputs are invalid for hephaes."""


class ConversionAuthoringInspectionError(ConversionAuthoringServiceError):
    """Raised when inspection of an asset fails."""


class ConversionAuthoringPreviewError(ConversionAuthoringServiceError):
    """Raised when preview generation fails."""


class ConversionAuthoringService:
    def __init__(self, workspace: Workspace, session: Session) -> None:
        self.workspace = workspace
        self.session = session

    def get_capabilities(self) -> ConversionAuthoringCapabilitiesResponse:
        # Keep the response shape backend-owned while reusing hephaes semantics.
        return ConversionAuthoringCapabilitiesResponse(hephaes=build_conversion_capabilities())

    def _get_asset_or_raise(self, asset_id: str):
        try:
            return self.workspace.get_asset_or_raise(asset_id)
        except AssetNotFoundError as exc:
            raise ConversionAuthoringNotFoundError(str(exc)) from exc

    @contextmanager
    def _open_asset_reader(self, asset_id: str):
        asset = self._get_asset_or_raise(asset_id)
        try:
            with open_asset_reader(asset.file_path) as reader:
                yield asset, reader
        except ConversionAuthoringServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive guard around reader opening
            raise ConversionAuthoringInspectionError(
                f"failed to open asset reader: {asset.file_name}"
            ) from exc

    def inspect_asset(self, request: ConversionInspectionRequest) -> InspectionResult:
        with self._open_asset_reader(request.asset_id) as (_asset, reader):
            try:
                return inspect_reader(
                    reader,
                    topics=request.topics or None,
                    sample_n=request.sample_n,
                    max_depth=request.max_depth,
                    max_sequence_items=request.max_sequence_items,
                    on_failure=request.on_failure,
                    topic_type_hints=request.topic_type_hints or None,
                )
            except Exception as exc:
                raise ConversionAuthoringInspectionError(
                    f"inspection failed for asset: {request.asset_id}"
                ) from exc

    def draft_asset(self, request: ConversionDraftRequest) -> tuple[InspectionResult, DraftSpecResult, str]:
        with self._open_asset_reader(request.asset_id) as (_asset, reader):
            try:
                inspection = inspect_reader(
                    reader,
                    topics=request.topics or None,
                    sample_n=request.sample_n,
                    max_depth=request.max_depth,
                    max_sequence_items=request.max_sequence_items,
                    on_failure=request.on_failure,
                    topic_type_hints=request.topic_type_hints or None,
                )
                draft = build_draft_conversion_spec(
                    inspection,
                    request=request.draft_request,
                    reader=reader,
                )
                draft_revision = self.workspace.record_conversion_draft_revision(
                    label=None,
                    saved_config_selector=None,
                    source_asset_selector=request.asset_id,
                    spec_document=draft.spec,
                    inspection_request=ConversionInspectionRequest(
                        asset_id=request.asset_id,
                        topics=list(request.topics),
                        sample_n=request.sample_n,
                        max_depth=request.max_depth,
                        max_sequence_items=request.max_sequence_items,
                        on_failure=request.on_failure,
                        topic_type_hints=dict(request.topic_type_hints),
                    ),
                    inspection=inspection,
                    draft_request=request.draft_request,
                    draft_result=draft,
                    preview=draft.preview,
                )
                return inspection, draft, draft_revision.id
            except ConversionAuthoringNotFoundError:
                raise
            except ValueError as exc:
                raise ConversionAuthoringValidationError(str(exc)) from exc
            except Exception as exc:
                raise ConversionAuthoringValidationError(
                    f"draft generation failed for asset: {request.asset_id}"
                ) from exc

    def preview_asset(self, request: ConversionPreviewRequest) -> PreviewResult:
        with self._open_asset_reader(request.asset_id) as (_asset, reader):
            try:
                return preview_conversion_spec(
                    reader,
                    request.spec,
                    sample_n=request.sample_n,
                    topic_type_hints=request.topic_type_hints or None,
                )
            except ValueError as exc:
                raise ConversionAuthoringValidationError(str(exc)) from exc
            except Exception as exc:
                raise ConversionAuthoringPreviewError(
                    f"preview generation failed for asset: {request.asset_id}"
                ) from exc
