"""Conversion routes for backend-managed hephaes workflows."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api._status import HTTP_422_UNPROCESSABLE_CONTENT
from app.db.models import Conversion
from app.db.session import get_db_session
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
from app.schemas.jobs import JobResponse
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
    ConversionNotFoundError,
    ConversionService,
    ConversionValidationError,
    get_conversion_or_raise,
    list_conversions_filtered,
)
from hephaes.models import ConversionSpec

router = APIRouter(prefix="/conversions", tags=["conversions"])
DbSession = Annotated[Session, Depends(get_db_session)]


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


def build_conversion_summary_response(conversion: Conversion) -> ConversionSummaryResponse:
    config_payload = dict(conversion.config_json)
    return ConversionSummaryResponse(
        id=conversion.id,
        job_id=conversion.job_id,
        status=conversion.status,
        asset_ids=list(conversion.source_asset_ids_json),
        config=config_payload,
        output_path=conversion.output_path,
        error_message=conversion.error_message,
        representation_policy=_build_representation_policy(config_payload),
        created_at=conversion.created_at,
        updated_at=conversion.updated_at,
    )


def build_conversion_detail_response(conversion: Conversion) -> ConversionDetailResponse:
    if conversion.job is None:  # pragma: no cover - defensive integrity guard
        raise ValueError(f"conversion is missing linked job: {conversion.id}")

    job_payload = JobResponse.model_validate(conversion.job).model_dump()
    config_payload = job_payload.get("config_json")
    if isinstance(config_payload, dict):
        job_payload["representation_policy"] = config_payload.get("representation_policy")

    return ConversionDetailResponse(
        **build_conversion_summary_response(conversion).model_dump(),
        output_files=list(conversion.output_files_json),
        job=JobResponse.model_validate(job_payload),
    )


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
    return ConversionDraftResponse(
        asset_id=request.asset_id,
        request=request,
        inspection=inspection,
        draft=draft,
        draft_revision_id=draft_revision_id,
        representation_policy=_representation_policy_from_spec(draft.spec),
    )


def build_preview_response(
    *,
    request: ConversionPreviewRequest,
    preview,
) -> ConversionPreviewResponse:
    return ConversionPreviewResponse(
        asset_id=request.asset_id,
        request=request,
        preview=preview,
        representation_policy=_representation_policy_from_spec(request.spec),
    )


@router.post("", response_model=ConversionDetailResponse, status_code=status.HTTP_201_CREATED)
def create_conversion_route(payload: ConversionCreateRequest, session: DbSession) -> ConversionDetailResponse:
    service = ConversionService(session)

    try:
        conversion = service.run_conversion(payload)
    except ConversionValidationError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except ConversionExecutionError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return build_conversion_detail_response(conversion)


@router.get("/capabilities", response_model=ConversionAuthoringCapabilitiesResponse)
def get_conversion_authoring_capabilities_route(session: DbSession) -> ConversionAuthoringCapabilitiesResponse:
    service = ConversionAuthoringService(session)
    return service.get_capabilities()


@router.post("/inspect", response_model=ConversionInspectionResponse)
def inspect_conversion_route(
    payload: ConversionInspectionRequest,
    session: DbSession,
) -> ConversionInspectionResponse:
    service = ConversionAuthoringService(session)

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
) -> ConversionDraftResponse:
    service = ConversionAuthoringService(session)

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
) -> ConversionPreviewResponse:
    service = ConversionAuthoringService(session)

    try:
        preview = service.preview_asset(payload)
    except ConversionAuthoringNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ConversionAuthoringValidationError, ConversionAuthoringPreviewError, ConversionAuthoringServiceError) as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return build_preview_response(request=payload, preview=preview)


@router.get("", response_model=list[ConversionSummaryResponse])
def list_conversions_route(
    session: DbSession,
    image_payload_contract: Annotated[str | None, Query()] = None,
    legacy_compatible: Annotated[bool | None, Query()] = None,
) -> list[ConversionSummaryResponse]:
    return [
        build_conversion_summary_response(conversion)
        for conversion in list_conversions_filtered(
            session,
            image_payload_contract=image_payload_contract,
            legacy_compatible=legacy_compatible,
        )
    ]


@router.get("/{conversion_id}", response_model=ConversionDetailResponse)
def get_conversion_route(conversion_id: str, session: DbSession) -> ConversionDetailResponse:
    try:
        conversion = get_conversion_or_raise(session, conversion_id)
    except ConversionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return build_conversion_detail_response(conversion)
