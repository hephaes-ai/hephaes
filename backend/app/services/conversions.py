"""Service helpers for backend-managed hephaes conversion workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.session import sessionmaker

from hephaes import (
    Converter,
    Workspace,
    build_legacy_conversion_spec,
    build_mapping_template,
    build_mapping_template_from_json,
)
from hephaes.models import (
    ConversionSpec,
    MappingTemplate,
    ParquetOutputConfig,
    ResampleConfig,
    TFRecordOutputConfig,
    Topic,
)

from app.config import get_settings
from app.db.models import Asset, Conversion, utc_now
from app.schemas.conversions import ConversionCreateRequest
from app.services.assets import AssetNotFoundError, get_asset_or_raise
from app.services.conversion_configs import (
    ConversionConfigInvalidError,
    ConversionConfigNotFoundError,
    ConversionConfigService,
)
from app.services.jobs import JobService
from app.services.outputs import sync_output_artifacts_for_conversion

_REPRESENTATION_POLICY_VERSION = 1


class ConversionServiceError(Exception):
    """Base exception for conversion workflow failures."""


class ConversionNotFoundError(ConversionServiceError):
    """Raised when a requested conversion cannot be found."""


class ConversionValidationError(ConversionServiceError):
    """Raised when conversion inputs are invalid for backend execution."""


class ConversionExecutionError(ConversionServiceError):
    """Raised when hephaes conversion fails during execution."""


@dataclass(frozen=True)
class PendingConversionExecution:
    conversion_id: str
    job_id: str
    asset_file_paths: list[str]
    mapping: MappingTemplate
    conversion_spec: ConversionSpec
    output_dir: Path


def list_conversions(session: Session) -> list[Conversion]:
    statement = (
        select(Conversion)
        .options(selectinload(Conversion.job))
        .order_by(Conversion.created_at.desc(), Conversion.id.desc())
    )
    return list(session.scalars(statement).all())


def list_conversions_filtered(
    session: Session,
    *,
    image_payload_contract: str | None = None,
    legacy_compatible: bool | None = None,
) -> list[Conversion]:
    conversions = list_conversions(session)
    if image_payload_contract is None and legacy_compatible is None:
        return conversions

    filtered: list[Conversion] = []
    for conversion in conversions:
        policy = conversion.config_json.get("representation_policy")
        if not isinstance(policy, dict):
            continue

        effective_contract = policy.get("effective_image_payload_contract")
        markers = policy.get("compatibility_markers")
        is_legacy_compatible = isinstance(markers, list) and "legacy_list_image_payload" in markers

        if image_payload_contract is not None and effective_contract != image_payload_contract:
            continue
        if legacy_compatible is not None and is_legacy_compatible != legacy_compatible:
            continue

        filtered.append(conversion)

    return filtered


def get_conversion(session: Session, conversion_id: str) -> Conversion | None:
    statement = (
        select(Conversion)
        .options(selectinload(Conversion.job))
        .where(Conversion.id == conversion_id)
    )
    return session.scalar(statement)


def get_conversion_or_raise(session: Session, conversion_id: str) -> Conversion:
    conversion = get_conversion(session, conversion_id)
    if conversion is None:
        raise ConversionNotFoundError(f"conversion not found: {conversion_id}")
    return conversion


def _topics_from_asset(asset: Asset) -> list[Topic]:
    metadata_record = asset.metadata_record
    if metadata_record is None:
        raise ConversionValidationError(
            f"asset must be indexed before conversion: {asset.file_name}"
        )

    try:
        topics = [
            Topic.model_validate(
                {
                    "name": topic_payload["name"],
                    "message_type": topic_payload["message_type"],
                    "message_count": topic_payload["message_count"],
                    "rate_hz": topic_payload["rate_hz"],
                }
            )
            for topic_payload in metadata_record.topics_json
        ]
    except Exception as exc:  # pragma: no cover - defensive guard around persisted data
        raise ConversionValidationError(
            f"asset metadata topics are invalid for conversion: {asset.file_name}"
        ) from exc

    if not topics:
        raise ConversionValidationError(
            f"asset has no indexed topics available for conversion: {asset.file_name}"
        )

    return topics


def _resolve_mapping(assets: list[Asset], request: ConversionCreateRequest) -> MappingTemplate:
    first_asset_topics = _topics_from_asset(assets[0])

    if request.mapping is None:
        if request.spec is not None and request.spec.mapping is not None:
            return request.spec.mapping
        return build_mapping_template(first_asset_topics)

    return build_mapping_template_from_json(
        first_asset_topics,
        request.mapping,
        strict_unknown_topics=True,
        require_all_topics=False,
    )


def _resolve_assets(session: Session, asset_ids: list[str]) -> list[Asset]:
    assets: list[Asset] = []
    workspace: Workspace | None = None
    for asset_id in asset_ids:
        try:
            assets.append(get_asset_or_raise(session, asset_id))
        except AssetNotFoundError as exc:
            if workspace is None:
                workspace = Workspace.open(get_settings().workspace_root)
            workspace_asset = workspace.get_asset(asset_id)
            if workspace_asset is None:
                raise ConversionValidationError(str(exc)) from exc

            workspace_metadata = workspace.get_asset_metadata(asset_id)
            metadata_record = None
            if workspace_metadata is not None:
                metadata_record = SimpleNamespace(
                    topics_json=[
                        {
                            "name": topic.name,
                            "message_type": topic.message_type,
                            "message_count": topic.message_count,
                            "rate_hz": topic.rate_hz,
                        }
                        for topic in workspace_metadata.topics
                    ]
                )

            assets.append(
                SimpleNamespace(
                    id=workspace_asset.id,
                    file_path=workspace_asset.file_path,
                    file_name=workspace_asset.file_name,
                    metadata_record=metadata_record,
                )
            )
    return assets


def _resolve_conversion_spec(
    request: ConversionCreateRequest,
    *,
    mapping: MappingTemplate,
) -> ConversionSpec:
    if request.spec is not None:
        if request.write_manifest is None:
            return request.spec
        return request.spec.model_copy(update={"write_manifest": request.write_manifest})

    output = _resolve_output_config(request)
    resample = (
        ResampleConfig.model_validate(request.resample.model_dump())
        if request.resample is not None
        else None
    )
    write_manifest = request.write_manifest if request.write_manifest is not None else True
    return build_legacy_conversion_spec(
        mapping=mapping,
        output=output,
        resample=resample,
        write_manifest=write_manifest,
    )


def _build_conversion_config(
    *,
    mapping: MappingTemplate,
    mapping_mode: str,
    spec: ConversionSpec,
    representation_policy: dict[str, object],
) -> dict[str, object]:
    return {
        "mapping": mapping.model_dump(),
        "mapping_mode": mapping_mode,
        "output": spec.to_output_config().model_dump(),
        "resample": spec.resample.model_dump() if spec.resample is not None else None,
        "write_manifest": spec.write_manifest,
        "spec": spec.model_dump(by_alias=True),
        "representation_policy": representation_policy,
    }


def _resolve_representation_policy(
    *,
    request: ConversionCreateRequest,
    spec: ConversionSpec,
) -> dict[str, object]:
    if spec.output.format != "tfrecord":
        if spec.output.image_payload_contract != "bytes_v2":
            raise ConversionValidationError(
                "image payload contract can only be customized for tfrecord output"
            )
        return {
            "policy_version": _REPRESENTATION_POLICY_VERSION,
            "output_format": "parquet",
            "requested_image_payload_contract": None,
            "effective_image_payload_contract": None,
            "payload_encoding": None,
            "null_encoding": None,
            "compatibility_markers": [],
            "warnings": [],
        }

    requested_contract: str | None = None
    if request.output is not None and request.output.format == "tfrecord":
        requested_contract = request.output.image_payload_contract
    elif request.spec is not None:
        requested_contract = request.spec.output.image_payload_contract

    effective_contract = spec.output.image_payload_contract
    compatibility_markers: list[str] = []
    warnings: list[str] = []
    if effective_contract == "legacy_list_v1":
        compatibility_markers.append("legacy_list_image_payload")
        warnings.append(
            "legacy image payload contract is enabled; image data will remain list-based"
        )

    return {
        "policy_version": _REPRESENTATION_POLICY_VERSION,
        "output_format": "tfrecord",
        "requested_image_payload_contract": requested_contract,
        "effective_image_payload_contract": effective_contract,
        "payload_encoding": spec.output.payload_encoding,
        "null_encoding": spec.output.null_encoding,
        "compatibility_markers": compatibility_markers,
        "warnings": warnings,
    }


def _resolve_output_config(
    request: ConversionCreateRequest,
) -> ParquetOutputConfig | TFRecordOutputConfig:
    if request.output is None:
        return ParquetOutputConfig()

    output_payload = request.output.model_dump()
    if request.output.format == "parquet":
        return ParquetOutputConfig.model_validate(output_payload)
    return TFRecordOutputConfig.model_validate(output_payload)


def _update_conversion_status(
    session: Session,
    *,
    conversion: Conversion,
    status: str,
    output_files: list[str] | None = None,
    error_message: str | None = None,
) -> Conversion:
    conversion.status = status
    conversion.output_files_json = list(output_files or [])
    conversion.error_message = error_message
    conversion.updated_at = utc_now()
    session.commit()
    return get_conversion_or_raise(session, conversion.id)


class ConversionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.job_service = JobService(session)
        self.settings = get_settings()

    def create_conversion(
        self,
        request: ConversionCreateRequest,
    ) -> tuple[Conversion, PendingConversionExecution]:
        assets = _resolve_assets(self.session, request.asset_ids)
        conversion_spec: ConversionSpec
        mapping_mode: str

        if request.saved_config_id is not None:
            config_service = ConversionConfigService(self.session)
            try:
                saved_config_document = config_service.resolve_saved_config_spec_document(
                    request.saved_config_id,
                    persist_migration=True,
                    mark_opened=True,
                )
            except ConversionConfigNotFoundError as exc:
                raise ConversionValidationError(str(exc)) from exc
            except ConversionConfigInvalidError as exc:
                raise ConversionValidationError(str(exc)) from exc

            conversion_spec = saved_config_document.spec
            if request.write_manifest is not None:
                conversion_spec = conversion_spec.model_copy(update={"write_manifest": request.write_manifest})
            representation_policy = _resolve_representation_policy(
                request=request,
                spec=conversion_spec,
            )
            mapping = conversion_spec.mapping or build_mapping_template(_topics_from_asset(assets[0]))
            mapping_mode = "saved-config"
            conversion_config = _build_conversion_config(
                mapping=mapping,
                mapping_mode=mapping_mode,
                spec=conversion_spec,
                representation_policy=representation_policy,
            )
            conversion_config["saved_config_id"] = request.saved_config_id
            conversion_config["saved_config_revision_number"] = config_service._get_config_or_raise(
                request.saved_config_id
            ).current_revision_number
            conversion_config["saved_config_spec_document_version"] = saved_config_document.spec_version
        else:
            mapping = _resolve_mapping(assets, request)
            conversion_spec = _resolve_conversion_spec(request, mapping=mapping)
            representation_policy = _resolve_representation_policy(
                request=request,
                spec=conversion_spec,
            )
            mapping_mode = "spec" if request.spec is not None else ("custom" if request.mapping is not None else "auto")
            conversion_config = _build_conversion_config(
                mapping=mapping,
                mapping_mode=mapping_mode,
                spec=conversion_spec,
                representation_policy=representation_policy,
            )

        conversion_id = str(uuid4())
        output_dir = self.settings.outputs_dir / "conversions" / conversion_id
        output_dir.mkdir(parents=True, exist_ok=True)

        job = self.job_service.create_job(
            job_type="convert",
            target_asset_ids=[asset.id for asset in assets],
            config={"execution": self.settings.job_execution_mode, **conversion_config},
            output_path=str(output_dir),
        )

        conversion = Conversion(
            id=conversion_id,
            job_id=job.id,
            status="queued",
            source_asset_ids_json=[asset.id for asset in assets],
            config_json=conversion_config,
            output_path=str(output_dir),
            output_files_json=[],
            error_message=None,
        )
        self.session.add(conversion)
        self.session.commit()

        return (
            get_conversion_or_raise(self.session, conversion.id),
            PendingConversionExecution(
                conversion_id=conversion_id,
                job_id=job.id,
                asset_file_paths=[asset.file_path for asset in assets],
                mapping=mapping,
                conversion_spec=conversion_spec,
                output_dir=output_dir,
            ),
        )

    def execute_conversion(self, execution: PendingConversionExecution) -> Conversion:
        conversion = get_conversion_or_raise(self.session, execution.conversion_id)
        self.job_service.mark_job_running(execution.job_id)
        conversion = _update_conversion_status(self.session, conversion=conversion, status="running")

        try:
            converter = Converter(
                file_paths=execution.asset_file_paths,
                mapping=execution.mapping,
                output_dir=execution.output_dir,
                spec=execution.conversion_spec,
                output=execution.conversion_spec.to_output_config(),
                resample=execution.conversion_spec.resample,
                write_manifest=execution.conversion_spec.write_manifest,
            )
            output_files = [str(path) for path in converter.convert()]
            self.job_service.mark_job_succeeded(execution.job_id, output_path=str(execution.output_dir))
            completed_conversion = _update_conversion_status(
                self.session,
                conversion=conversion,
                status="succeeded",
                output_files=output_files,
                error_message=None,
            )
            sync_output_artifacts_for_conversion(self.session, completed_conversion, commit=True)
            return get_conversion_or_raise(self.session, completed_conversion.id)
        except Exception as exc:
            self.session.rollback()
            self.job_service.mark_job_failed(execution.job_id, error_message=str(exc))
            failed_conversion = get_conversion_or_raise(self.session, execution.conversion_id)
            _update_conversion_status(
                self.session,
                conversion=failed_conversion,
                status="failed",
                output_files=failed_conversion.output_files_json,
                error_message=str(exc),
            )
            raise ConversionExecutionError(str(exc)) from exc

    def run_conversion(self, request: ConversionCreateRequest) -> Conversion:
        conversion, execution = self.create_conversion(request)
        return self.execute_conversion(execution)



def run_conversion_job_in_background(
    session_factory: sessionmaker[Session],
    *,
    execution: PendingConversionExecution,
) -> None:
    session = session_factory()
    try:
        ConversionService(session).execute_conversion(execution)
    finally:
        session.close()
