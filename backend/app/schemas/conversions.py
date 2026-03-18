"""Pydantic schemas for conversion requests and responses."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.jobs import JobResponse

ConversionStatus = Literal["queued", "running", "succeeded", "failed"]
ParquetCompression = Literal["none", "snappy", "gzip", "brotli", "lz4", "zstd"]
TFRecordCompression = Literal["none", "gzip"]
TFRecordNullEncoding = Literal["presence_flag"]
TFRecordPayloadEncoding = Literal["typed_features"]
ResampleStrategy = Literal["interpolate", "downsample"]


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
    output: ConversionOutputRequest = Field(
        default_factory=ParquetConversionOutputRequest,
    )
    mapping: dict[str, list[str]] | None = None
    resample: ConversionResampleRequest | None = None
    write_manifest: bool = True

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


class ConversionSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    status: ConversionStatus
    asset_ids: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    output_path: str | None = None
    error_message: str | None = None
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
