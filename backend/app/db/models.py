"""SQLAlchemy models for the backend application."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

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
