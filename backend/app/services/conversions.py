"""Service helpers for backend-managed hephaes conversion workflows."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from hephaes import Converter, build_mapping_template, build_mapping_template_from_json
from hephaes.models import (
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
from app.services.jobs import JobService
from app.services.outputs import sync_output_artifacts_for_conversion


class ConversionServiceError(Exception):
    """Base exception for conversion workflow failures."""


class ConversionNotFoundError(ConversionServiceError):
    """Raised when a requested conversion cannot be found."""


class ConversionValidationError(ConversionServiceError):
    """Raised when conversion inputs are invalid for backend execution."""


class ConversionExecutionError(ConversionServiceError):
    """Raised when hephaes conversion fails during execution."""


def list_conversions(session: Session) -> list[Conversion]:
    statement = (
        select(Conversion)
        .options(selectinload(Conversion.job))
        .order_by(Conversion.created_at.desc(), Conversion.id.desc())
    )
    return list(session.scalars(statement).all())


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
        return build_mapping_template(first_asset_topics)

    return build_mapping_template_from_json(
        first_asset_topics,
        request.mapping,
        strict_unknown_topics=True,
        require_all_topics=False,
    )


def _resolve_assets(session: Session, asset_ids: list[str]) -> list[Asset]:
    assets: list[Asset] = []
    for asset_id in asset_ids:
        try:
            assets.append(get_asset_or_raise(session, asset_id))
        except AssetNotFoundError as exc:
            raise ConversionValidationError(str(exc)) from exc
    return assets


def _build_conversion_config(
    request: ConversionCreateRequest,
    *,
    mapping: MappingTemplate,
) -> dict[str, object]:
    return {
        "mapping": mapping.model_dump(),
        "mapping_mode": "custom" if request.mapping is not None else "auto",
        "output": request.output.model_dump(),
        "resample": request.resample.model_dump() if request.resample is not None else None,
        "write_manifest": request.write_manifest,
    }


def _resolve_output_config(request: ConversionCreateRequest) -> ParquetOutputConfig | TFRecordOutputConfig:
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

    def run_conversion(self, request: ConversionCreateRequest) -> Conversion:
        assets = _resolve_assets(self.session, request.asset_ids)
        mapping = _resolve_mapping(assets, request)
        conversion_config = _build_conversion_config(request, mapping=mapping)

        conversion_id = str(uuid4())
        output_dir = self.settings.outputs_dir / "conversions" / conversion_id
        output_dir.mkdir(parents=True, exist_ok=True)

        job = self.job_service.create_job(
            job_type="convert",
            target_asset_ids=[asset.id for asset in assets],
            config={"execution": "inline", **conversion_config},
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

        self.job_service.mark_job_running(job.id)
        conversion = _update_conversion_status(self.session, conversion=conversion, status="running")

        try:
            converter = Converter(
                file_paths=[asset.file_path for asset in assets],
                mapping=mapping,
                output_dir=output_dir,
                output=_resolve_output_config(request),
                resample=(
                    ResampleConfig.model_validate(request.resample.model_dump())
                    if request.resample is not None
                    else None
                ),
                write_manifest=request.write_manifest,
            )
            output_files = [str(path) for path in converter.convert()]
            self.job_service.mark_job_succeeded(job.id, output_path=str(output_dir))
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
            self.job_service.mark_job_failed(job.id, error_message=str(exc))
            failed_conversion = get_conversion_or_raise(self.session, conversion_id)
            _update_conversion_status(
                self.session,
                conversion=failed_conversion,
                status="failed",
                output_files=failed_conversion.output_files_json,
                error_message=str(exc),
            )
            raise ConversionExecutionError(str(exc)) from exc
