from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from ...conversion.spec_io import ConversionSpecDocument, dump_conversion_spec_document
from ...models import ConversionSpec
from ..errors import (
    ConversionConfigAlreadyExistsError,
    WorkspaceError,
)
from ..models import SavedConversionConfig
from ..serialization import build_saved_conversion_config, row_to_saved_conversion_config_summary, to_db_timestamp
from ..utils import (
    _build_config_document_relative_path,
    _load_conversion_document_input,
    _normalize_name,
    _normalize_optional_text,
    _utc_now,
    _write_text_atomically,
)


class WorkspaceConfigMutationMixin:
    def _insert_saved_conversion_config(
        self,
        connection: sqlite3.Connection,
        *,
        name: str,
        spec_document: ConversionSpecDocument | ConversionSpec | dict | str | Path,
        description: str | None = None,
        timestamp=None,
        config_id: str | None = None,
    ) -> SavedConversionConfig:
        normalized_name = _normalize_name(name)
        if not normalized_name:
            raise WorkspaceError("saved conversion config name must be non-empty")

        document = _load_conversion_document_input(spec_document)
        config_id = config_id or str(uuid4())
        relative_document_path = _build_config_document_relative_path(config_id)
        document_path = self.paths.specs_dir / relative_document_path
        timestamp = timestamp or _utc_now()
        payload = dump_conversion_spec_document(document, format="json")
        description_value = _normalize_optional_text(description)

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
                description_value,
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
            description=description_value,
            document=document,
            timestamp=timestamp,
        )
        row = connection.execute(
            "SELECT * FROM conversion_configs WHERE id = ?",
            (config_id,),
        ).fetchone()
        assert row is not None

        summary = row_to_saved_conversion_config_summary(
            row,
            document_path=str(document_path),
        )
        return build_saved_conversion_config(summary, document=document)

    def save_conversion_config(
        self,
        *,
        name: str,
        spec_document: ConversionSpecDocument | ConversionSpec | dict | str | Path,
        description: str | None = None,
    ) -> SavedConversionConfig:
        with self._transaction() as connection:
            return self._insert_saved_conversion_config(
                connection,
                name=name,
                spec_document=spec_document,
                description=description,
            )

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
