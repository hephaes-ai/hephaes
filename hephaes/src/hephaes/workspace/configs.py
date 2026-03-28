from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from ..conversion.spec_io import (
    CONVERSION_SPEC_DOCUMENT_VERSION,
    ConversionSpecDocument,
    dump_conversion_spec_document,
    load_conversion_spec_document,
    migrate_conversion_spec_document,
)
from ..models import ConversionSpec
from .errors import (
    ConversionConfigAlreadyExistsError,
    ConversionConfigInvalidError,
    ConversionConfigNotFoundError,
    WorkspaceError,
)
from .models import (
    SavedConversionConfig,
    SavedConversionConfigRevision,
    SavedConversionConfigRevisionSummary,
    SavedConversionConfigSummary,
)
from .serialization import (
    build_saved_conversion_config,
    build_saved_conversion_config_revision,
    from_db_timestamp,
    row_to_saved_conversion_config_revision_summary,
    row_to_saved_conversion_config_summary,
    to_db_timestamp,
)
from .utils import (
    _build_config_document_relative_path,
    _build_config_revision_relative_path,
    _load_conversion_document_input,
    _normalize_name,
    _normalize_optional_text,
    _utc_now,
    _write_text_atomically,
)


class WorkspaceConfigMixin:
    def list_saved_conversion_configs(self) -> list[SavedConversionConfigSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM conversion_configs
                ORDER BY updated_at DESC, id DESC
                """
            ).fetchall()
        return [
            row_to_saved_conversion_config_summary(
                row,
                document_path=str(self.paths.specs_dir / row["spec_document_path"]),
            )
            for row in rows
        ]

    def get_saved_conversion_config(self, config_id: str) -> SavedConversionConfig | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversion_configs WHERE id = ?",
                (config_id,),
            ).fetchone()
        if row is None:
            return None
        summary = row_to_saved_conversion_config_summary(
            row,
            document_path=str(self.paths.specs_dir / row["spec_document_path"]),
        )
        return self._resolve_saved_conversion_config(summary, persist_migration=True)

    def find_saved_conversion_config_by_name(self, name: str) -> SavedConversionConfigSummary | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversion_configs WHERE normalized_name = ?",
                (_normalize_name(name),),
            ).fetchone()
        if row is None:
            return None
        return row_to_saved_conversion_config_summary(
            row,
            document_path=str(self.paths.specs_dir / row["spec_document_path"]),
        )

    def resolve_saved_conversion_config(self, selector: str) -> SavedConversionConfig:
        config = self.get_saved_conversion_config(selector)
        if config is not None:
            return config
        summary = self.find_saved_conversion_config_by_name(selector)
        if summary is None:
            raise ConversionConfigNotFoundError(f"saved conversion config not found: {selector}")
        return self._resolve_saved_conversion_config(summary, persist_migration=True)

    def save_conversion_config(
        self,
        *,
        name: str,
        spec_document: ConversionSpecDocument | ConversionSpec | dict | str | Path,
        description: str | None = None,
    ) -> SavedConversionConfig:
        normalized_name = _normalize_name(name)
        if not normalized_name:
            raise WorkspaceError("saved conversion config name must be non-empty")

        document = _load_conversion_document_input(spec_document)

        config_id = str(uuid4())
        relative_document_path = _build_config_document_relative_path(config_id)
        document_path = self.paths.specs_dir / relative_document_path
        timestamp = _utc_now()
        payload = dump_conversion_spec_document(document, format="json")

        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT id FROM conversion_configs WHERE normalized_name = ?",
                (normalized_name,),
            ).fetchone()
            if existing is not None:
                raise ConversionConfigAlreadyExistsError(
                    f"saved conversion config already exists: {name}"
                )

            _write_text_atomically(document_path, payload)
            connection.execute(
                """
                INSERT INTO conversion_configs(
                    id,
                    name,
                    normalized_name,
                    description,
                    metadata_json,
                    spec_document_path,
                    spec_document_version,
                    invalid_reason,
                    created_at,
                    updated_at,
                    last_opened_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    config_id,
                    name.strip(),
                    normalized_name,
                    _normalize_optional_text(description),
                    json.dumps(document.metadata),
                    relative_document_path,
                    document.spec_version,
                    None,
                    to_db_timestamp(timestamp),
                    to_db_timestamp(timestamp),
                    None,
                ),
            )
            self._insert_conversion_config_revision(
                connection,
                config_id=config_id,
                revision_number=1,
                description=_normalize_optional_text(description),
                document=document,
                timestamp=timestamp,
            )
            row = connection.execute(
                "SELECT * FROM conversion_configs WHERE id = ?",
                (config_id,),
            ).fetchone()

        summary = row_to_saved_conversion_config_summary(
            row,
            document_path=str(document_path),
        )
        return build_saved_conversion_config(summary, document=document)

    def update_saved_conversion_config(
        self,
        selector: str,
        *,
        spec_document: ConversionSpecDocument | ConversionSpec | dict | str | Path,
        name: str | None = None,
        description: str | None = None,
    ) -> SavedConversionConfig:
        current = self.resolve_saved_conversion_config(selector)
        resolved_name = _normalize_optional_text(name) or current.name
        normalized_name = _normalize_name(resolved_name)
        if not normalized_name:
            raise WorkspaceError("saved conversion config name must be non-empty")

        document = _load_conversion_document_input(spec_document)
        payload = dump_conversion_spec_document(document, format="json")
        timestamp = _utc_now()
        description_value = description if description is not None else current.description

        with self._transaction() as connection:
            self._ensure_saved_conversion_config_has_revision_history(
                current.id,
                connection=connection,
            )
            existing = connection.execute(
                "SELECT id FROM conversion_configs WHERE normalized_name = ? AND id != ?",
                (normalized_name, current.id),
            ).fetchone()
            if existing is not None:
                raise ConversionConfigAlreadyExistsError(
                    f"saved conversion config already exists: {resolved_name}"
                )

            _write_text_atomically(Path(current.document_path), payload)
            revision_number = self._next_conversion_config_revision_number(connection, current.id)
            connection.execute(
                """
                UPDATE conversion_configs
                SET name = ?, normalized_name = ?, description = ?, metadata_json = ?,
                    spec_document_version = ?, invalid_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    resolved_name,
                    normalized_name,
                    _normalize_optional_text(description_value),
                    json.dumps(document.metadata),
                    document.spec_version,
                    None,
                    to_db_timestamp(timestamp),
                    current.id,
                ),
            )
            self._insert_conversion_config_revision(
                connection,
                config_id=current.id,
                revision_number=revision_number,
                description=_normalize_optional_text(description_value),
                document=document,
                timestamp=timestamp,
            )

        return self.resolve_saved_conversion_config(current.id)

    def duplicate_saved_conversion_config(
        self,
        selector: str,
        *,
        name: str,
        description: str | None = None,
    ) -> SavedConversionConfig:
        source = self.resolve_saved_conversion_config(selector)
        return self.save_conversion_config(
            name=name,
            spec_document=source.document,
            description=description if description is not None else source.description,
        )

    def list_saved_conversion_config_revisions(
        self,
        selector: str,
    ) -> list[SavedConversionConfigRevisionSummary]:
        config = self.resolve_saved_conversion_config(selector)
        self._ensure_saved_conversion_config_has_revision_history(config.id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM conversion_config_revisions
                WHERE config_id = ?
                ORDER BY revision_number DESC, id DESC
                """,
                (config.id,),
            ).fetchall()
        return [
            row_to_saved_conversion_config_revision_summary(
                row,
                document_path=str(self.paths.specs_dir / row["spec_document_path"]),
            )
            for row in rows
        ]

    def get_saved_conversion_config_revision(
        self,
        revision_id: str,
    ) -> SavedConversionConfigRevision | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversion_config_revisions WHERE id = ?",
                (revision_id,),
            ).fetchone()
        if row is None:
            return None
        summary = row_to_saved_conversion_config_revision_summary(
            row,
            document_path=str(self.paths.specs_dir / row["spec_document_path"]),
        )
        return self._resolve_saved_conversion_config_revision(summary, persist_migration=True)

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

    def _get_saved_conversion_config_summary_or_raise(
        self,
        config_id: str,
    ) -> SavedConversionConfigSummary:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversion_configs WHERE id = ?",
                (config_id,),
            ).fetchone()
        if row is None:
            raise ConversionConfigNotFoundError(f"saved conversion config not found: {config_id}")
        return row_to_saved_conversion_config_summary(
            row,
            document_path=str(self.paths.specs_dir / row["spec_document_path"]),
        )

    def _get_saved_conversion_config_revision_summary_or_raise(
        self,
        revision_id: str,
    ) -> SavedConversionConfigRevisionSummary:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversion_config_revisions WHERE id = ?",
                (revision_id,),
            ).fetchone()
        if row is None:
            raise ConversionConfigNotFoundError(
                f"saved conversion config revision not found: {revision_id}"
            )
        return row_to_saved_conversion_config_revision_summary(
            row,
            document_path=str(self.paths.specs_dir / row["spec_document_path"]),
        )

    def _latest_saved_conversion_config_revision_id(self, config_id: str) -> str | None:
        self._ensure_saved_conversion_config_has_revision_history(config_id)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM conversion_config_revisions
                WHERE config_id = ?
                ORDER BY revision_number DESC, id DESC
                LIMIT 1
                """,
                (config_id,),
            ).fetchone()
        return row["id"] if row is not None else None

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

    def _next_conversion_config_revision_number(
        self,
        connection: sqlite3.Connection,
        config_id: str,
    ) -> int:
        row = connection.execute(
            """
            SELECT COALESCE(MAX(revision_number), 0) AS max_revision_number
            FROM conversion_config_revisions
            WHERE config_id = ?
            """,
            (config_id,),
        ).fetchone()
        return int(row["max_revision_number"]) + 1

    def _ensure_saved_conversion_config_has_revision_history(
        self,
        config_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        owns_connection = connection is None
        connection_cm = None
        if connection is None:
            connection_cm = self._transaction()
            connection = connection_cm.__enter__()
        try:
            row = connection.execute(
                """
                SELECT COALESCE(COUNT(*), 0) AS revision_count
                FROM conversion_config_revisions
                WHERE config_id = ?
                """,
                (config_id,),
            ).fetchone()
            if int(row["revision_count"]) > 0:
                return

            config_row = connection.execute(
                "SELECT * FROM conversion_configs WHERE id = ?",
                (config_id,),
            ).fetchone()
            if config_row is None:
                raise ConversionConfigNotFoundError(
                    f"saved conversion config not found: {config_id}"
                )

            document_path = self.paths.specs_dir / config_row["spec_document_path"]
            document = load_conversion_spec_document(document_path)
            timestamp = from_db_timestamp(config_row["updated_at"])
            self._insert_conversion_config_revision(
                connection,
                config_id=config_id,
                revision_number=1,
                description=config_row["description"],
                document=document,
                timestamp=timestamp,
            )
        except Exception as exc:
            if owns_connection and connection_cm is not None:
                connection_cm.__exit__(type(exc), exc, exc.__traceback__)
            raise
        else:
            if owns_connection and connection_cm is not None:
                connection_cm.__exit__(None, None, None)

    def _insert_conversion_config_revision(
        self,
        connection: sqlite3.Connection,
        *,
        config_id: str,
        revision_number: int,
        description: str | None,
        document: ConversionSpecDocument,
        timestamp: datetime,
    ) -> None:
        revision_id = str(uuid4())
        relative_document_path = _build_config_revision_relative_path(revision_id)
        document_path = self.paths.specs_dir / relative_document_path
        _write_text_atomically(
            document_path,
            dump_conversion_spec_document(document, format="json"),
        )
        connection.execute(
            """
            INSERT INTO conversion_config_revisions(
                id,
                config_id,
                revision_number,
                description,
                metadata_json,
                spec_document_path,
                spec_document_version,
                invalid_reason,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                revision_id,
                config_id,
                revision_number,
                description,
                json.dumps(document.metadata),
                relative_document_path,
                document.spec_version,
                None,
                to_db_timestamp(timestamp),
            ),
        )
