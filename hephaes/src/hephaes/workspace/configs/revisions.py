from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from uuid import uuid4

from ...conversion.spec_io import ConversionSpecDocument, dump_conversion_spec_document, load_conversion_spec_document
from ..errors import ConversionConfigNotFoundError
from ..serialization import from_db_timestamp, to_db_timestamp
from ..utils import _build_config_revision_relative_path, _write_text_atomically


class WorkspaceConfigRevisionMixin:
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
