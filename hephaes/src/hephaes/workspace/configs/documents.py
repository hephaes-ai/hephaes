from __future__ import annotations

from pathlib import Path

from ...conversion.spec_io import (
    CONVERSION_SPEC_DOCUMENT_VERSION,
    dump_conversion_spec_document,
    load_conversion_spec_document,
    migrate_conversion_spec_document,
)
from ..errors import ConversionConfigInvalidError
from ..models import SavedConversionConfig, SavedConversionConfigRevision, SavedConversionConfigRevisionSummary, SavedConversionConfigSummary
from ..serialization import build_saved_conversion_config, build_saved_conversion_config_revision, to_db_timestamp
from ..utils import _utc_now, _write_text_atomically


class WorkspaceConfigDocumentMixin:
    def _resolve_saved_conversion_config(
        self,
        summary: SavedConversionConfigSummary,
        *,
        persist_migration: bool,
    ) -> SavedConversionConfig:
        document_path = Path(summary.document_path)
        try:
            document = load_conversion_spec_document(document_path)
        except Exception as exc:
            if persist_migration:
                self._update_saved_conversion_config_invalid_reason(summary.id, str(exc))
            raise ConversionConfigInvalidError(str(exc)) from exc

        needs_migration = document.spec_version < CONVERSION_SPEC_DOCUMENT_VERSION
        if needs_migration and persist_migration:
            migrated_document = migrate_conversion_spec_document(document)
            _write_text_atomically(
                document_path,
                dump_conversion_spec_document(migrated_document, format="json"),
            )
            previous_version = summary.spec_document_version
            migration_note = (
                f"migrated saved config from spec document version {previous_version} "
                f"to {migrated_document.spec_version}"
            )
            timestamp = _utc_now()
            with self._transaction() as connection:
                self._ensure_saved_conversion_config_has_revision_history(
                    summary.id,
                    connection=connection,
                )
                connection.execute(
                    """
                    UPDATE conversion_configs
                    SET spec_document_version = ?, invalid_reason = ?, updated_at = ?, last_opened_at = ?
                    WHERE id = ?
                    """,
                    (
                        migrated_document.spec_version,
                        None,
                        to_db_timestamp(timestamp),
                        to_db_timestamp(timestamp),
                        summary.id,
                    ),
                )
                self._insert_conversion_config_revision(
                    connection,
                    config_id=summary.id,
                    revision_number=self._next_conversion_config_revision_number(
                        connection, summary.id
                    ),
                    description=migration_note,
                    document=migrated_document,
                    timestamp=timestamp,
                )
            refreshed_summary = self._get_saved_conversion_config_summary_or_raise(summary.id)
            return build_saved_conversion_config(refreshed_summary, document=migrated_document)

        if persist_migration:
            self._update_saved_conversion_config_metadata(
                summary.id,
                spec_document_version=document.spec_version,
                invalid_reason=None,
                mark_opened=True,
            )
            summary = self._get_saved_conversion_config_summary_or_raise(summary.id)

        return build_saved_conversion_config(summary, document=document)

    def _resolve_saved_conversion_config_revision(
        self,
        summary: SavedConversionConfigRevisionSummary,
        *,
        persist_migration: bool,
    ) -> SavedConversionConfigRevision:
        document_path = Path(summary.document_path)
        try:
            document = load_conversion_spec_document(document_path)
        except Exception as exc:
            if persist_migration:
                self._update_saved_conversion_config_revision_invalid_reason(summary.id, str(exc))
            raise ConversionConfigInvalidError(str(exc)) from exc

        needs_migration = document.spec_version < CONVERSION_SPEC_DOCUMENT_VERSION
        if needs_migration and persist_migration:
            migrated_document = migrate_conversion_spec_document(document)
            _write_text_atomically(
                document_path,
                dump_conversion_spec_document(migrated_document, format="json"),
            )
            self._update_saved_conversion_config_revision_metadata(
                summary.id,
                spec_document_version=migrated_document.spec_version,
                invalid_reason=None,
            )
            refreshed_summary = self._get_saved_conversion_config_revision_summary_or_raise(summary.id)
            return build_saved_conversion_config_revision(
                refreshed_summary,
                document=migrated_document,
            )

        if persist_migration:
            self._update_saved_conversion_config_revision_metadata(
                summary.id,
                spec_document_version=document.spec_version,
                invalid_reason=None,
            )
            summary = self._get_saved_conversion_config_revision_summary_or_raise(summary.id)

        return build_saved_conversion_config_revision(summary, document=document)

    def _update_saved_conversion_config_invalid_reason(self, config_id: str, invalid_reason: str) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE conversion_configs
                SET invalid_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    invalid_reason,
                    to_db_timestamp(_utc_now()),
                    config_id,
                ),
            )

    def _update_saved_conversion_config_revision_invalid_reason(
        self,
        revision_id: str,
        invalid_reason: str,
    ) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE conversion_config_revisions
                SET invalid_reason = ?
                WHERE id = ?
                """,
                (
                    invalid_reason,
                    revision_id,
                ),
            )

    def _update_saved_conversion_config_metadata(
        self,
        config_id: str,
        *,
        spec_document_version: int,
        invalid_reason: str | None,
        mark_opened: bool,
    ) -> None:
        timestamp = _utc_now()
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE conversion_configs
                SET spec_document_version = ?, invalid_reason = ?, updated_at = ?, last_opened_at = ?
                WHERE id = ?
                """,
                (
                    spec_document_version,
                    invalid_reason,
                    to_db_timestamp(timestamp),
                    to_db_timestamp(timestamp) if mark_opened else None,
                    config_id,
                ),
            )

    def _update_saved_conversion_config_revision_metadata(
        self,
        revision_id: str,
        *,
        spec_document_version: int,
        invalid_reason: str | None,
    ) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE conversion_config_revisions
                SET spec_document_version = ?, invalid_reason = ?
                WHERE id = ?
                """,
                (
                    spec_document_version,
                    invalid_reason,
                    revision_id,
                ),
            )
