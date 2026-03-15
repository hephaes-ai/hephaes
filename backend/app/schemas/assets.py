"""Pydantic schemas for asset-related API requests and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

IndexingStatus = Literal["pending", "indexing", "indexed", "failed"]


class AssetRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(min_length=1)

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("file_path must be non-empty")
        return stripped


class AssetSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    file_type: str = Field(min_length=1)
    file_size: int = Field(ge=0)
    registered_time: datetime
    indexing_status: IndexingStatus
    last_indexed_time: datetime | None = None


class AssetListItem(AssetSummary):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AssetRegistrationResponse(AssetSummary):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AssetDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: AssetSummary
