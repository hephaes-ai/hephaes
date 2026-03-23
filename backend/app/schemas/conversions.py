"""Pydantic schemas for conversion requests and responses."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.jobs import JobResponse
from hephaes.models import ConversionSpec

ConversionStatus = Literal["queued", "running", "succeeded", "failed"]
ParquetCompression = Literal["none", "snappy", "gzip", "brotli", "lz4", "zstd"]
TFRecordCompression = Literal["none", "gzip"]
TFRecordNullEncoding = Literal["presence_flag"]
TFRecordPayloadEncoding = Literal["typed_features"]
TFRecordImagePayloadContract = Literal["bytes_v2", "legacy_list_v1"]
ResampleStrategy = Literal["interpolate", "downsample"]


class ConversionRepresentationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version: int = Field(default=1, ge=1)
    output_format: Literal["parquet", "tfrecord"]
    requested_image_payload_contract: TFRecordImagePayloadContract | None = None
    image_payload_contract: TFRecordImagePayloadContract | None = None
    payload_encoding: TFRecordPayloadEncoding | None = None
    null_encoding: TFRecordNullEncoding | None = None
    compatibility_markers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ParquetConversionOutputRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["parquet"] = "parquet"
    compression: ParquetCompression = "none"


class TFRecordConversionOutputRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["tfrecord"] = "tfrecord"
    compression: TFRecordCompression = "none"
    payload_encoding: TFRecordPayloadEncoding = "typed_features"
    null_encoding: TFRecordNullEncoding = "presence_flag"
    image_payload_contract: TFRecordImagePayloadContract = "bytes_v2"


ConversionOutputRequest = Annotated[
    ParquetConversionOutputRequest | TFRecordConversionOutputRequest,
    Field(discriminator="format"),
]


class ConversionResampleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    freq_hz: float = Field(gt=0)
    method: ResampleStrategy


class ConversionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_ids: list[str] = Field(min_length=1)
    saved_config_id: str | None = None
    spec: ConversionSpec | None = None
    output: ConversionOutputRequest | None = None
    mapping: dict[str, list[str]] | None = None
    resample: ConversionResampleRequest | None = None
    write_manifest: bool | None = None

    @field_validator("asset_ids", mode="before")
    @classmethod
    def normalize_asset_ids(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [item.strip() if isinstance(item, str) else item for item in value]

    @field_validator("asset_ids")
    @classmethod
    def validate_asset_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("asset_ids must not be empty")
        if any(not asset_id for asset_id in value):
            raise ValueError("asset_ids must contain non-empty values")
        if len(set(value)) != len(value):
            raise ValueError("asset_ids must not contain duplicates")
        return value

    @field_validator("saved_config_id", mode="before")
    @classmethod
    def normalize_saved_config_id(cls, value: object) -> object:
        if value is None or not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            return None
        return stripped

    @model_validator(mode="after")
    def validate_mapping_payload(self) -> "ConversionCreateRequest":
        if self.mapping is None:
            return self

        if not self.mapping:
            raise ValueError("mapping must not be empty when provided")

        for target_field, source_topics in self.mapping.items():
            if not target_field:
                raise ValueError("mapping target field names must be non-empty")
            if not source_topics:
                raise ValueError("mapping source topic lists must be non-empty")
            if any(not topic for topic in source_topics):
                raise ValueError("mapping source topic names must be non-empty")

        return self

    @model_validator(mode="after")
    def validate_spec_payload(self) -> "ConversionCreateRequest":
        if self.saved_config_id is not None and self.spec is not None:
            raise ValueError("saved_config_id cannot be combined with an inline spec")

        if self.saved_config_id is not None:
            if self.mapping is not None or self.output is not None or self.resample is not None:
                raise ValueError(
                    "saved_config_id cannot be combined with legacy mapping, output, or resample fields"
                )
            return self

        if self.spec is None:
            return self

        if (
            self.spec.output.format != "tfrecord"
            and self.spec.output.image_payload_contract != "bytes_v2"
        ):
            raise ValueError(
                "spec.output.image_payload_contract can only be customized for tfrecord output"
            )

        if self.mapping is not None or self.output is not None or self.resample is not None:
            raise ValueError(
                "spec cannot be combined with legacy mapping, output, or resample fields"
            )

        return self


class ConversionSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    status: ConversionStatus
    asset_ids: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    output_path: str | None = None
    error_message: str | None = None
    representation_policy: ConversionRepresentationPolicy | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def normalize_datetimes_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)


class ConversionDetailResponse(ConversionSummaryResponse):
    model_config = ConfigDict(extra="forbid")

    output_files: list[str] = Field(default_factory=list)
    job: JobResponse
