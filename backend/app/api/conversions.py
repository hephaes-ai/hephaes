"""Conversion routes for backend-managed hephaes workflows."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api._status import HTTP_422_UNPROCESSABLE_CONTENT
from app.dependencies import get_db_session, get_workspace
from app.mappers.workspace import map_conversion_detail, map_conversion_summary
from app.schemas.conversion_authoring import (
    ConversionAuthoringCapabilitiesResponse,
    ConversionDraftRequest,
    ConversionDraftResponse,
    ConversionInspectionRequest,
    ConversionInspectionResponse,
    ConversionPreviewRequest,
    ConversionPreviewResponse,
)
from app.schemas.conversions import (
    ConversionRepresentationPolicy,
    ConversionCreateRequest,
    ConversionDetailResponse,
    ConversionSummaryResponse,
)
from app.services.conversion_authoring import (
    ConversionAuthoringInspectionError,
    ConversionAuthoringNotFoundError,
    ConversionAuthoringPreviewError,
    ConversionAuthoringService,
    ConversionAuthoringServiceError,
    ConversionAuthoringValidationError,
)
from app.services.conversions import (
    ConversionExecutionError,
    ConversionService,
    ConversionValidationError,
    run_conversion_job_in_background,
)
from hephaes import Workspace
from hephaes._converter_helpers import _normalize_payload
from hephaes.models import ConversionSpec
from hephaes.conversion.draft_spec import DraftSpecResult
from hephaes.conversion.preview import PreviewResult

router = APIRouter(prefix="/conversions", tags=["conversions"])
DbSession = Annotated[Session, Depends(get_db_session)]
WorkspaceDep = Annotated[Workspace, Depends(get_workspace)]


def _build_representation_policy(config: dict[str, object]) -> ConversionRepresentationPolicy | None:
    persisted_policy = config.get("representation_policy")
    if isinstance(persisted_policy, dict):
        policy_payload = dict(persisted_policy)
        if "effective_image_payload_contract" in policy_payload and "image_payload_contract" not in policy_payload:
            policy_payload["image_payload_contract"] = policy_payload["effective_image_payload_contract"]
        policy_payload.pop("effective_image_payload_contract", None)
        return ConversionRepresentationPolicy.model_validate(policy_payload)

    output_payload: dict[str, object] | None = None
    spec_payload = config.get("spec")
    if isinstance(spec_payload, dict):
        spec_output = spec_payload.get("output")
        if isinstance(spec_output, dict):
            output_payload = spec_output

    if output_payload is None:
        raw_output = config.get("output")
        if isinstance(raw_output, dict):
            output_payload = raw_output

    if output_payload is None:
        return None

    output_format = output_payload.get("format", "parquet")
    if output_format != "tfrecord":
        return ConversionRepresentationPolicy(output_format="parquet")

    image_payload_contract = str(output_payload.get("image_payload_contract", "bytes_v2"))
    compatibility_markers: list[str] = []
    if image_payload_contract == "legacy_list_v1":
        compatibility_markers.append("legacy_list_image_payload")

    return ConversionRepresentationPolicy(
        output_format="tfrecord",
        requested_image_payload_contract=None,
        image_payload_contract=image_payload_contract,  # type: ignore[arg-type]
        payload_encoding=output_payload.get("payload_encoding", "typed_features"),  # type: ignore[arg-type]
        null_encoding=output_payload.get("null_encoding", "presence_flag"),  # type: ignore[arg-type]
        compatibility_markers=compatibility_markers,
        warnings=[],
    )


def _representation_policy_from_spec(spec: ConversionSpec | None) -> ConversionRepresentationPolicy:
    if spec is None:
        return ConversionRepresentationPolicy(
            output_format="tfrecord",
            requested_image_payload_contract=None,
            image_payload_contract="bytes_v2",
            payload_encoding="typed_features",
            null_encoding="presence_flag",
            compatibility_markers=[],
            warnings=[],
        )

    if spec.output.format != "tfrecord":
        return ConversionRepresentationPolicy(output_format="parquet")

    compatibility_markers: list[str] = []
    warnings: list[str] = []
    if spec.output.image_payload_contract == "legacy_list_v1":
        compatibility_markers.append("legacy_list_image_payload")
        warnings.append(
            "legacy image payload contract is enabled; image data will remain list-based"
        )

    return ConversionRepresentationPolicy(
        output_format="tfrecord",
        requested_image_payload_contract=spec.output.image_payload_contract,
        image_payload_contract=spec.output.image_payload_contract,
        payload_encoding=spec.output.payload_encoding,
        null_encoding=spec.output.null_encoding,
        compatibility_markers=compatibility_markers,
        warnings=warnings,
    )


def _json_safe_preview(preview: PreviewResult | None) -> PreviewResult | None:
    if preview is None:
        return None
    normalized = _normalize_payload(preview.model_dump(mode="python", by_alias=True))
    return PreviewResult.model_validate(normalized)


def _json_safe_draft_result(draft: DraftSpecResult) -> DraftSpecResult:
    safe_preview = _json_safe_preview(draft.preview)
    return draft.model_copy(update={"preview": safe_preview})
def _matches_conversion_filters(
    config: dict[str, object],
    *,
    image_payload_contract: str | None,
    legacy_compatible: bool | None,
) -> bool:
    if image_payload_contract is None and legacy_compatible is None:
        return True

    policy = _build_representation_policy(config)
    if policy is None:
        return False
    if image_payload_contract is not None and policy.image_payload_contract != image_payload_contract:
        return False
    if legacy_compatible is not None:
        is_legacy_compatible = "legacy_list_image_payload" in policy.compatibility_markers
        if is_legacy_compatible != legacy_compatible:
            return False
    return True


def build_inspection_response(
    *,
    request: ConversionInspectionRequest,
    inspection,
) -> ConversionInspectionResponse:
    return ConversionInspectionResponse(
        asset_id=request.asset_id,
        request=request,
        inspection=inspection,
        representation_policy=_representation_policy_from_spec(None),
    )


def build_draft_response(
    *,
    request: ConversionDraftRequest,
    inspection,
    draft,
    draft_revision_id: str | None = None,
) -> ConversionDraftResponse:
    safe_draft = _json_safe_draft_result(draft)
    return ConversionDraftResponse(
        asset_id=request.asset_id,
        request=request,
        inspection=inspection,
        draft=safe_draft,
        draft_revision_id=draft_revision_id,
        representation_policy=_representation_policy_from_spec(safe_draft.spec),
    )


def build_preview_response(
    *,
    request: ConversionPreviewRequest,
    preview,
) -> ConversionPreviewResponse:
    safe_preview = _json_safe_preview(preview)
    assert safe_preview is not None
    return ConversionPreviewResponse(
        asset_id=request.asset_id,
        request=request,
        preview=safe_preview,
        representation_policy=_representation_policy_from_spec(request.spec),
    )


@router.post("", response_model=ConversionDetailResponse, status_code=status.HTTP_201_CREATED)
def create_conversion_route(
    payload: ConversionCreateRequest,
    request: Request,
    workspace: WorkspaceDep,
) -> ConversionDetailResponse:
    service = ConversionService(workspace)

    try:
        conversion, execution = service.create_conversion(payload)
    except ConversionValidationError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    try:
        request.app.state.job_runner.submit(
            f"convert assets for conversion {conversion.id}",
            run_conversion_job_in_background,
            workspace,
            execution=execution,
        )
    except ConversionExecutionError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    run = workspace.get_conversion_run(conversion.id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"conversion run not found after execution: {conversion.id}",
        )
    return map_conversion_detail(
        run,
        job=workspace.get_job(run.job_id) if run.job_id is not None else None,
    )


@router.get("/capabilities", response_model=ConversionAuthoringCapabilitiesResponse)
def get_conversion_authoring_capabilities_route(
    workspace: WorkspaceDep,
    session: DbSession,
) -> ConversionAuthoringCapabilitiesResponse:
    service = ConversionAuthoringService(workspace, session)
    return service.get_capabilities()


@router.post("/inspect", response_model=ConversionInspectionResponse)
def inspect_conversion_route(
    payload: ConversionInspectionRequest,
    session: DbSession,
    workspace: WorkspaceDep,
) -> ConversionInspectionResponse:
    service = ConversionAuthoringService(workspace, session)

    try:
        inspection = service.inspect_asset(payload)
    except ConversionAuthoringNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ConversionAuthoringValidationError, ConversionAuthoringInspectionError, ConversionAuthoringServiceError) as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return build_inspection_response(request=payload, inspection=inspection)


@router.post("/draft", response_model=ConversionDraftResponse)
def draft_conversion_route(
    payload: ConversionDraftRequest,
    session: DbSession,
    workspace: WorkspaceDep,
) -> ConversionDraftResponse:
    service = ConversionAuthoringService(workspace, session)

    try:
        inspection, draft, draft_revision_id = service.draft_asset(payload)
    except ConversionAuthoringNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ConversionAuthoringValidationError, ConversionAuthoringInspectionError, ConversionAuthoringServiceError) as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return build_draft_response(
        request=payload,
        inspection=inspection,
        draft=draft,
        draft_revision_id=draft_revision_id,
    )


@router.post("/preview", response_model=ConversionPreviewResponse)
def preview_conversion_route(
    payload: ConversionPreviewRequest,
    session: DbSession,
    workspace: WorkspaceDep,
) -> ConversionPreviewResponse:
    service = ConversionAuthoringService(workspace, session)

    try:
        preview = service.preview_asset(payload)
    except ConversionAuthoringNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ConversionAuthoringValidationError, ConversionAuthoringPreviewError, ConversionAuthoringServiceError) as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return build_preview_response(request=payload, preview=preview)


@router.get("", response_model=list[ConversionSummaryResponse])
def list_conversions_route(
    workspace: WorkspaceDep,
    image_payload_contract: Annotated[str | None, Query()] = None,
    legacy_compatible: Annotated[bool | None, Query()] = None,
) -> list[ConversionSummaryResponse]:
    return [
        map_conversion_summary(run)
        for run in workspace.list_conversion_runs()
        if _matches_conversion_filters(
            dict(run.config),
            image_payload_contract=image_payload_contract,
            legacy_compatible=legacy_compatible,
        )
    ]


@router.get("/{conversion_id}", response_model=ConversionDetailResponse)
def get_conversion_route(
    conversion_id: str,
    workspace: WorkspaceDep,
) -> ConversionDetailResponse:
    run = workspace.get_conversion_run(conversion_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"conversion not found: {conversion_id}",
        )
    return map_conversion_detail(
        run,
        job=workspace.get_job(run.job_id) if run.job_id is not None else None,
    )
