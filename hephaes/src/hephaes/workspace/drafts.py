from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .._converter_helpers import _normalize_payload
from ..conversion.spec_io import (
    CONVERSION_SPEC_DOCUMENT_VERSION,
    ConversionSpecDocument,
    dump_conversion_spec_document,
    load_conversion_spec_document,
    migrate_conversion_spec_document,
)
from ..models import ConversionSpec
from .errors import ConversionConfigInvalidError, ConversionConfigNotFoundError
from .models import ConversionDraftRevision, ConversionDraftRevisionSummary
from .serialization import (
    build_conversion_draft_revision,
    row_to_conversion_draft_revision_summary,
    to_db_timestamp,
)
from .utils import (
    _build_draft_revision_relative_path,
    _load_conversion_document_input,
    _normalize_optional_text,
    _utc_now,
    _write_text_atomically,
)


class WorkspaceDraftMixin:
    def record_conversion_draft_revision(
        self,
        *,
        spec_document: ConversionSpecDocument | ConversionSpec | dict | str | Path,
        label: str | None = None,
        saved_config_selector: str | None = None,
        source_asset_selector: str | Path | None = None,
        inspection_request: dict[str, Any] | Any | None = None,
        inspection: dict[str, Any] | Any | None = None,
        draft_request: dict[str, Any] | Any | None = None,
        draft_result: dict[str, Any] | Any | None = None,
        preview: dict[str, Any] | Any | None = None,
    ) -> ConversionDraftRevision:
        def _json_safe_payload(value: dict[str, Any] | Any | None) -> dict[str, Any]:
            if value is None:
                return {}
            if isinstance(value, dict):
                normalized = _normalize_payload(value)
                if not isinstance(normalized, dict):
                    raise TypeError("draft revision payloads must normalize to dictionaries")
                return dict(normalized)
            if hasattr(value, "model_dump"):
                normalized = _normalize_payload(value.model_dump(mode="python", by_alias=True))
                if not isinstance(normalized, dict):
                    raise TypeError("draft revision payloads must normalize to dictionaries")
                return dict(normalized)
            raise TypeError("draft revision payloads must be dicts or model-like objects")

        def _json_safe_optional_payload(
            value: dict[str, Any] | Any | None,
        ) -> dict[str, Any] | None:
            if value is None:
                return None
            if isinstance(value, dict):
                normalized = _normalize_payload(value)
                if not isinstance(normalized, dict):
                    raise TypeError("draft revision payloads must normalize to dictionaries")
                return dict(normalized)
            if hasattr(value, "model_dump"):
                normalized = _normalize_payload(value.model_dump(mode="python", by_alias=True))
                if not isinstance(normalized, dict):
                    raise TypeError("draft revision payloads must normalize to dictionaries")
                return dict(normalized)
            raise TypeError("draft revision payloads must be dicts or model-like objects")

        document = _load_conversion_document_input(spec_document)
        draft_head_id = str(uuid4())
        revision_id = str(uuid4())
        relative_document_path = _build_draft_revision_relative_path(revision_id)
        document_path = self.paths.specs_dir / relative_document_path
        timestamp = _utc_now()
        saved_config = (
            self.resolve_saved_conversion_config(saved_config_selector)
            if saved_config_selector is not None
            else None
        )
        saved_config_id = saved_config.id if saved_config is not None else None
        source_asset_id = (
            self.resolve_asset(source_asset_selector).id
            if source_asset_selector is not None
            else None
        )
        revision_number = (
            len(self.list_conversion_draft_revisions(saved_config_selector=saved_config_id)) + 1
            if saved_config_id is not None
            else 1
        )
        status = "saved" if saved_config_id is not None else "draft"
        preview_payload = _json_safe_optional_payload(preview)

        with self._transaction() as connection:
            _write_text_atomically(
                document_path,
                dump_conversion_spec_document(document, format="json"),
            )
            connection.execute(
                """
                INSERT INTO conversion_drafts(
                    id,
                    source_asset_id,
                    status,
                    current_revision_id,
                    confirmed_revision_id,
                    saved_config_id,
                    created_at,
                    updated_at,
                    discarded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_head_id,
                    source_asset_id,
                    status,
                    revision_id,
                    revision_id if status == "saved" else None,
                    saved_config_id,
                    to_db_timestamp(timestamp),
                    to_db_timestamp(timestamp),
                    None,
                ),
            )
            connection.execute(
                """
                INSERT INTO conversion_draft_revisions(
                    id,
                    draft_id,
                    revision_number,
                    label,
                    saved_config_id,
                    source_asset_id,
                    status,
                    metadata_json,
                    inspection_request_json,
                    inspection_json,
                    draft_request_json,
                    draft_result_json,
                    preview_request_json,
                    preview_json,
                    spec_document_path,
                    spec_document_version,
                    invalid_reason,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    revision_id,
                    draft_head_id,
                    revision_number,
                    _normalize_optional_text(label),
                    saved_config_id,
                    source_asset_id,
                    status,
                    json.dumps(document.metadata),
                    json.dumps(_json_safe_payload(inspection_request)),
                    json.dumps(_json_safe_payload(inspection)),
                    json.dumps(_json_safe_payload(draft_request)),
                    json.dumps(_json_safe_payload(draft_result)),
                    json.dumps({}),
                    json.dumps(preview_payload) if preview_payload is not None else None,
                    relative_document_path,
                    document.spec_version,
                    None,
                    to_db_timestamp(timestamp),
                    to_db_timestamp(timestamp),
                ),
            )
            row = connection.execute(
                "SELECT * FROM conversion_draft_revisions WHERE id = ?",
                (revision_id,),
            ).fetchone()

        summary = row_to_conversion_draft_revision_summary(
            row,
            document_path=str(document_path),
        )
        return build_conversion_draft_revision(summary, document=document)

    def list_conversion_draft_revisions(
        self,
        *,
        saved_config_selector: str | None = None,
        source_asset_selector: str | Path | None = None,
    ) -> list[ConversionDraftRevisionSummary]:
        where_clauses: list[str] = []
        params: list[str] = []
        if saved_config_selector is not None:
            where_clauses.append("saved_config_id = ?")
            params.append(self.resolve_saved_conversion_config(saved_config_selector).id)
        if source_asset_selector is not None:
            where_clauses.append("source_asset_id = ?")
            params.append(self.resolve_asset(source_asset_selector).id)
        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM conversion_draft_revisions
                {where_sql}
                ORDER BY created_at DESC, id DESC
                """,
                params,
            ).fetchall()
        return [
            row_to_conversion_draft_revision_summary(
                row,
                document_path=str(self.paths.specs_dir / row["spec_document_path"]),
            )
            for row in rows
        ]

    def get_conversion_draft_revision(
        self,
        draft_id: str,
    ) -> ConversionDraftRevision | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversion_draft_revisions WHERE id = ?",
                (draft_id,),
            ).fetchone()
        if row is None:
            return None
        summary = row_to_conversion_draft_revision_summary(
            row,
            document_path=str(self.paths.specs_dir / row["spec_document_path"]),
        )
        return self._resolve_conversion_draft_revision(summary, persist_migration=True)

    def _resolve_conversion_draft_revision(
        self,
        summary: ConversionDraftRevisionSummary,
        *,
        persist_migration: bool,
    ) -> ConversionDraftRevision:
        document_path = Path(summary.document_path)
        try:
            document = load_conversion_spec_document(document_path)
        except Exception as exc:
            if persist_migration:
                self._update_conversion_draft_revision_invalid_reason(summary.id, str(exc))
            raise ConversionConfigInvalidError(str(exc)) from exc

        needs_migration = document.spec_version < CONVERSION_SPEC_DOCUMENT_VERSION
        if needs_migration and persist_migration:
            migrated_document = migrate_conversion_spec_document(document)
            _write_text_atomically(
                document_path,
                dump_conversion_spec_document(migrated_document, format="json"),
            )
            self._update_conversion_draft_revision_metadata(
                summary.id,
                spec_document_version=migrated_document.spec_version,
                invalid_reason=None,
            )
            refreshed_summary = self._get_conversion_draft_revision_summary_or_raise(summary.id)
            return build_conversion_draft_revision(
                refreshed_summary,
                document=migrated_document,
            )

        if persist_migration:
            self._update_conversion_draft_revision_metadata(
                summary.id,
                spec_document_version=document.spec_version,
                invalid_reason=None,
            )
            summary = self._get_conversion_draft_revision_summary_or_raise(summary.id)

        return build_conversion_draft_revision(summary, document=document)

    def _get_conversion_draft_revision_summary_or_raise(
        self,
        draft_id: str,
    ) -> ConversionDraftRevisionSummary:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversion_draft_revisions WHERE id = ?",
                (draft_id,),
            ).fetchone()
        if row is None:
            raise ConversionConfigNotFoundError(
                f"conversion draft revision not found: {draft_id}"
            )
        return row_to_conversion_draft_revision_summary(
            row,
            document_path=str(self.paths.specs_dir / row["spec_document_path"]),
        )

    def _update_conversion_draft_revision_invalid_reason(
        self,
        draft_id: str,
        invalid_reason: str,
    ) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE conversion_draft_revisions
                SET invalid_reason = ?
                WHERE id = ?
                """,
                (
                    invalid_reason,
                    draft_id,
                ),
            )

    def _update_conversion_draft_revision_metadata(
        self,
        draft_id: str,
        *,
        spec_document_version: int,
        invalid_reason: str | None,
    ) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE conversion_draft_revisions
                SET spec_document_version = ?, invalid_reason = ?
                WHERE id = ?
                """,
                (
                    spec_document_version,
                    invalid_reason,
                    draft_id,
                ),
            )
