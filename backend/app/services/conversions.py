"""Service helpers for backend-managed hephaes conversion workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from hephaes import (
    AssetNotFoundError,
    Converter,
    ConversionConfigNotFoundError as WorkspaceConversionConfigNotFoundError,
    ConversionRun,
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

from app.config import Settings, get_settings
from app.schemas.conversions import ConversionCreateRequest

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
    asset_ids: list[str]
    asset_file_paths: list[str]
    source_asset_paths: list[str]
    mapping: MappingTemplate
    conversion_spec: ConversionSpec
    output_dir: Path
    saved_config_id: str | None


def list_conversions(_session=None) -> list[ConversionRun]:
    return _workspace().list_conversion_runs()


def list_conversions_filtered(
    _session=None,
    *,
    image_payload_contract: str | None = None,
    legacy_compatible: bool | None = None,
) -> list[ConversionRun]:
    conversions = list_conversions()
    if image_payload_contract is None and legacy_compatible is None:
        return conversions

    filtered: list[ConversionRun] = []
    for conversion in conversions:
        policy = conversion.config.get("representation_policy")
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


def get_conversion(_session, conversion_id: str) -> ConversionRun | None:
    return _workspace().get_conversion_run(conversion_id)


def get_conversion_or_raise(_session, conversion_id: str) -> ConversionRun:
    conversion = get_conversion(_session, conversion_id)
    if conversion is None:
        raise ConversionNotFoundError(f"conversion not found: {conversion_id}")
    return conversion


def _topics_from_asset(workspace: Workspace, asset_id: str) -> list[Topic]:
    asset = workspace.get_asset_or_raise(asset_id)
    metadata = workspace.get_asset_metadata(asset_id)
    if metadata is None:
        raise ConversionValidationError(
            f"asset must be indexed before conversion: {asset.file_name}"
        )

    topics = [
        Topic(
            name=topic.name,
            message_type=topic.message_type,
            message_count=topic.message_count,
            rate_hz=topic.rate_hz,
        )
        for topic in metadata.topics
    ]
    if not topics:
        raise ConversionValidationError(
            f"asset has no indexed topics available for conversion: {asset.file_name}"
        )
    return topics


def _resolve_mapping(
    workspace: Workspace,
    asset_ids: list[str],
    request: ConversionCreateRequest,
) -> MappingTemplate:
    first_asset_topics = _topics_from_asset(workspace, asset_ids[0])

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


def _resolve_assets(workspace: Workspace, asset_ids: list[str]):
    assets = []
    for asset_id in asset_ids:
        try:
            assets.append(workspace.get_asset_or_raise(asset_id))
        except AssetNotFoundError as exc:
            raise ConversionValidationError(str(exc)) from exc
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
class ConversionService:
    def __init__(self, workspace: Workspace, settings: Settings | None = None) -> None:
        self.workspace = workspace
        self.settings = settings or get_settings()

    def create_conversion(
        self,
        request: ConversionCreateRequest,
    ) -> tuple[ConversionRun, PendingConversionExecution]:
        assets = _resolve_assets(self.workspace, request.asset_ids)
        conversion_spec: ConversionSpec
        mapping_mode: str
        saved_config_revision_id: str | None = None

        if request.saved_config_id is not None:
            try:
                saved_config = self.workspace.resolve_saved_conversion_config(request.saved_config_id)
            except WorkspaceConversionConfigNotFoundError as exc:
                raise ConversionValidationError(str(exc)) from exc

            revisions = self.workspace.list_saved_conversion_config_revisions(saved_config.id)
            saved_config_revision_number = revisions[0].revision_number if revisions else 1
            saved_config_revision_id = revisions[0].id if revisions else None
            saved_config_document = saved_config.document

            conversion_spec = saved_config_document.spec
            if request.write_manifest is not None:
                conversion_spec = conversion_spec.model_copy(
                    update={"write_manifest": request.write_manifest}
                )
            representation_policy = _resolve_representation_policy(
                request=request,
                spec=conversion_spec,
            )
            mapping = conversion_spec.mapping or build_mapping_template(
                _topics_from_asset(self.workspace, assets[0].id)
            )
            mapping_mode = "saved-config"
            conversion_config = _build_conversion_config(
                mapping=mapping,
                mapping_mode=mapping_mode,
                spec=conversion_spec,
                representation_policy=representation_policy,
            )
            conversion_config["saved_config_id"] = request.saved_config_id
            conversion_config["saved_config_revision_number"] = saved_config_revision_number
            conversion_config["saved_config_spec_document_version"] = saved_config_document.spec_version
        else:
            mapping = _resolve_mapping(self.workspace, [asset.id for asset in assets], request)
            conversion_spec = _resolve_conversion_spec(request, mapping=mapping)
            representation_policy = _resolve_representation_policy(
                request=request,
                spec=conversion_spec,
            )
            mapping_mode = (
                "spec"
                if request.spec is not None
                else ("custom" if request.mapping is not None else "auto")
            )
            conversion_config = _build_conversion_config(
                mapping=mapping,
                mapping_mode=mapping_mode,
                spec=conversion_spec,
                representation_policy=representation_policy,
            )

        conversion_id = str(uuid4())
        output_dir = self.settings.outputs_dir / "conversions" / conversion_id
        output_dir.mkdir(parents=True, exist_ok=True)

        asset_ids = [asset.id for asset in assets]
        asset_file_paths = [asset.file_path for asset in assets]
        source_asset_paths = [asset.source_path or asset.file_path for asset in assets]

        job = self.workspace.create_job(
            kind="conversion",
            target_asset_ids=asset_ids,
            config={
                "execution": self.settings.job_execution_mode,
                **conversion_config,
                "output_path": str(output_dir),
            },
        )
        self.workspace.create_conversion_run(
            run_id=conversion_id,
            job_id=job.id,
            source_asset_ids=asset_ids,
            source_asset_paths=source_asset_paths,
            output_dir=output_dir,
            saved_config_id=request.saved_config_id,
            saved_config_revision_id=saved_config_revision_id,
            config=dict(conversion_config),
        )

        run = self.workspace.get_conversion_run_or_raise(conversion_id)
        return (
            run,
            PendingConversionExecution(
                conversion_id=conversion_id,
                job_id=job.id,
                asset_ids=asset_ids,
                asset_file_paths=asset_file_paths,
                source_asset_paths=source_asset_paths,
                mapping=mapping,
                conversion_spec=conversion_spec,
                output_dir=output_dir,
                saved_config_id=request.saved_config_id,
            ),
        )

    def execute_conversion(self, execution: PendingConversionExecution) -> ConversionRun:
        self.workspace.mark_job_running(execution.job_id)
        self.workspace.mark_conversion_run_running(execution.conversion_id)

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
            artifact_paths = [
                str(path)
                for path in sorted(execution.output_dir.glob("*"))
                if path.is_file()
            ]
            outputs = self.workspace.register_output_artifacts(
                output_root=execution.output_dir,
                paths=artifact_paths,
                conversion_run_id=execution.conversion_id,
                source_asset_id=(
                    execution.asset_ids[0] if len(execution.asset_ids) == 1 else None
                ),
                source_asset_path=(
                    execution.source_asset_paths[0]
                    if len(execution.source_asset_paths) == 1
                    else None
                ),
                saved_config_id=execution.saved_config_id,
            )
            self.workspace.mark_conversion_run_succeeded(
                execution.conversion_id,
                output_paths=[output.output_path for output in outputs] or output_files,
            )
            self.workspace.mark_job_succeeded(
                execution.job_id,
                conversion_run_id=execution.conversion_id,
            )
            return self.workspace.get_conversion_run_or_raise(execution.conversion_id)
        except Exception as exc:
            self.workspace.mark_job_failed(execution.job_id, error_message=str(exc))
            self.workspace.mark_conversion_run_failed(
                execution.conversion_id,
                error_message=str(exc),
            )
            raise ConversionExecutionError(str(exc)) from exc

    def run_conversion(self, request: ConversionCreateRequest) -> ConversionRun:
        conversion, execution = self.create_conversion(request)
        del conversion
        return self.execute_conversion(execution)


def run_conversion_job_in_background(
    workspace: Workspace,
    *,
    execution: PendingConversionExecution,
) -> None:
    ConversionService(workspace).execute_conversion(execution)
