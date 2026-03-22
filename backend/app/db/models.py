"""SQLAlchemy models for the backend application."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from hephaes.conversion.spec_io import CONVERSION_SPEC_DOCUMENT_VERSION

ASSET_INDEXING_STATUSES = ("pending", "indexing", "indexed", "failed")
JOB_TYPES = ("index", "convert", "prepare_visualization")
JOB_STATUSES = ("queued", "running", "succeeded", "failed")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for backend database models."""


asset_tags_table = Table(
    "asset_tags",
    Base.metadata,
    Column("asset_id", String(36), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    UniqueConstraint("asset_id", "tag_id", name="uq_asset_tags_asset_id_tag_id"),
)


class Asset(Base):
    """Registered local file that the backend can index and operate on."""

    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint("file_size >= 0", name="ck_assets_file_size_non_negative"),
        CheckConstraint(
            "indexing_status IN ('pending', 'indexing', 'indexed', 'failed')",
            name="ck_assets_indexing_status_valid",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    file_path: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_type: Mapped[str] = mapped_column(String, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    registered_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    indexing_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
    )
    last_indexed_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_record: Mapped["AssetMetadata | None"] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        uselist=False,
    )
    tags: Mapped[list["Tag"]] = relationship(
        secondary=asset_tags_table,
        back_populates="assets",
        order_by="Tag.normalized_name",
    )


class AssetMetadata(Base):
    """Indexed metadata extracted from a registered asset."""

    __tablename__ = "asset_metadata"
    __table_args__ = (
        CheckConstraint("duration >= 0", name="ck_asset_metadata_duration_non_negative"),
        CheckConstraint("topic_count >= 0", name="ck_asset_metadata_topic_count_non_negative"),
        CheckConstraint("message_count >= 0", name="ck_asset_metadata_message_count_non_negative"),
    )

    asset_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    topic_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sensor_types_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    topics_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    default_episode_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    visualization_summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    raw_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    indexing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    asset: Mapped[Asset] = relationship(back_populates="metadata_record")


class Tag(Base):
    """User-defined label for organizing registered assets."""

    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("normalized_name", name="uq_tags_normalized_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    assets: Mapped[list[Asset]] = relationship(
        secondary=asset_tags_table,
        back_populates="tags",
    )


class Job(Base):
    """Durable record for background-capable indexing and conversion work."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "type IN ('index', 'convert', 'prepare_visualization')",
            name="ck_jobs_type_valid",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_jobs_status_valid",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    target_asset_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output_path: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    conversion: Mapped["Conversion | None"] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Conversion(Base):
    """Durable record for a backend-managed hephaes conversion run."""

    __tablename__ = "conversions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_conversions_status_valid",
        ),
        UniqueConstraint("job_id", name="uq_conversions_job_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    source_asset_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output_path: Mapped[str | None] = mapped_column(String, nullable=True)
    output_files_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    job: Mapped[Job] = relationship(back_populates="conversion")
    output_artifacts: Mapped[list["OutputArtifact"]] = relationship(
        back_populates="conversion",
        cascade="all, delete-orphan",
        order_by="OutputArtifact.created_at.desc()",
    )


class ConversionConfig(Base):
    """Durable reusable conversion config stored as JSON-backed spec documents."""

    __tablename__ = "conversion_configs"
    __table_args__ = (
        UniqueConstraint("normalized_name", name="uq_conversion_configs_normalized_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    spec_document_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    spec_document_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=CONVERSION_SPEC_DOCUMENT_VERSION,
    )
    current_revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    latest_preview_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    latest_preview_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalid_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    migration_notes_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    revisions: Mapped[list["ConversionConfigRevision"]] = relationship(
        back_populates="config",
        cascade="all, delete-orphan",
        order_by="ConversionConfigRevision.revision_number.desc()",
    )
    draft_revisions: Mapped[list["ConversionDraftRevision"]] = relationship(
        back_populates="saved_config",
        cascade="all, delete-orphan",
        order_by="ConversionDraftRevision.created_at.desc()",
    )


class ConversionConfigRevision(Base):
    """Immutable history entry for a saved conversion config."""

    __tablename__ = "conversion_config_revisions"
    __table_args__ = (
        CheckConstraint(
            "revision_number >= 1",
            name="ck_conversion_config_revisions_revision_number_positive",
        ),
        UniqueConstraint(
            "config_id",
            "revision_number",
            name="uq_conversion_config_revisions_config_id_revision_number",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    config_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversion_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    change_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="create")
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    spec_document_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    spec_document_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=CONVERSION_SPEC_DOCUMENT_VERSION,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    config: Mapped[ConversionConfig] = relationship(back_populates="revisions")


class ConversionDraftRevision(Base):
    """Persisted draft generated from inspection and preview data."""

    __tablename__ = "conversion_draft_revisions"
    __table_args__ = (
        CheckConstraint(
            "revision_number >= 1",
            name="ck_conversion_draft_revisions_revision_number_positive",
        ),
        CheckConstraint(
            "status IN ('draft', 'saved', 'discarded')",
            name="ck_conversion_draft_revisions_status_valid",
        ),
        UniqueConstraint(
            "saved_config_id",
            "revision_number",
            name="uq_conversion_draft_revisions_saved_config_id_revision_number",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    saved_config_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("conversion_configs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_asset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    inspection_request_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    inspection_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    draft_request_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    draft_result_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    spec_document_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    spec_document_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=CONVERSION_SPEC_DOCUMENT_VERSION,
    )
    preview_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    warning_messages_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    assumption_messages_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    unresolved_fields_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    saved_config: Mapped[ConversionConfig | None] = relationship(back_populates="draft_revisions")
    source_asset: Mapped[Asset | None] = relationship()


class OutputArtifact(Base):
    """Durable record for one emitted file from a conversion output directory."""

    __tablename__ = "output_artifacts"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="ck_output_artifacts_size_bytes_non_negative"),
        CheckConstraint(
            "availability_status IN ('ready', 'missing', 'invalid')",
            name="ck_output_artifacts_availability_status_valid",
        ),
        UniqueConstraint(
            "conversion_id",
            "relative_path",
            name="uq_output_artifacts_conversion_id_relative_path",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    conversion_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_asset_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    relative_path: Mapped[str] = mapped_column(String, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    media_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    availability_status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready", index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    conversion: Mapped[Conversion] = relationship(back_populates="output_artifacts")
    output_actions: Mapped[list["OutputAction"]] = relationship(
        back_populates="output_artifact",
        cascade="all, delete-orphan",
        order_by="OutputAction.created_at.desc()",
    )


class OutputAction(Base):
    """Durable record for one output-scoped compute action."""

    __tablename__ = "output_actions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_output_actions_status_valid",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    output_artifact_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("output_artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output_path: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    output_artifact: Mapped[OutputArtifact] = relationship(back_populates="output_actions")
