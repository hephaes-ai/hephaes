"""SQLAlchemy models for the backend application."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

ASSET_INDEXING_STATUSES = ("pending", "indexing", "indexed", "failed")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for backend database models."""


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
