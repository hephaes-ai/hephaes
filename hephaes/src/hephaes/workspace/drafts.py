from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Literal
from uuid import uuid4

from .._converter_helpers import _normalize_payload
from ..conversion.draft_spec import DraftSpecRequest, DraftSpecResult, build_draft_conversion_spec
from ..conversion.introspection import InspectionRequest, InspectionResult, inspect_reader
from ..conversion.preview import PreviewResult, preview_conversion_spec
from ..conversion.spec_io import (
    CONVERSION_SPEC_DOCUMENT_VERSION,
    ConversionSpecDocument,
    dump_conversion_spec_document,
    load_conversion_spec_document,
    migrate_conversion_spec_document,
)
from ..models import ConversionSpec
from ..reader import RosReader
from .errors import (
    AssetReadError,
    ConversionConfigInvalidError,
    ConversionDraftConfirmationError,
    ConversionDraftNotFoundError,
    ConversionDraftRevisionNotFoundError,
    ConversionDraftStateError,
)
from .models import (
    ConversionDraft,
    ConversionDraftRevision,
    ConversionDraftRevisionSummary,
    ConversionDraftSummary,
    SavedConversionConfig,
)
from .serialization import (
    build_conversion_draft,
    build_conversion_draft_revision,
    row_to_conversion_draft_revision_summary,
    row_to_conversion_draft_summary,
    to_db_timestamp,
)
from .utils import (
    _build_draft_revision_relative_path,
    _load_conversion_document_input,
    _normalize_optional_text,
    _utc_now,
    _write_text_atomically,
)

DraftStatus = Literal["draft", "confirmed", "saved", "discarded"]
RevisionStatus = Literal["draft", "saved", "discarded"]


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


def _json_safe_optional_payload(value: dict[str, Any] | Any | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return _json_safe_payload(value)


def _coerce_inspection_request(
    request: InspectionRequest | dict[str, Any] | None,
) -> InspectionRequest:
    if request is None:
        return InspectionRequest()
    if isinstance(request, InspectionRequest):
        return request
    return InspectionRequest.model_validate(request)


def _coerce_draft_request(
    request: DraftSpecRequest | dict[str, Any] | None,
) -> DraftSpecRequest:
    if request is None:
        return DraftSpecRequest()
    if isinstance(request, DraftSpecRequest):
        return request
    return DraftSpecRequest.model_validate(request)


def _build_draft_result_payload(draft_result: DraftSpecResult) -> dict[str, Any]:
    return draft_result.model_dump(
        mode="python",
        exclude={"request", "spec", "preview"},
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
        """Compatibility helper that records one draft with one initial revision."""

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
        status: RevisionStatus = "saved" if saved_config_id is not None else "draft"
        timestamp = _utc_now()

        with self._transaction() as connection:
            draft = self._create_conversion_draft(
                connection,
                source_asset_id=source_asset_id,
                status=status,
                saved_config_id=saved_config_id,
                timestamp=timestamp,
            )
            revision = self._append_conversion_draft_revision(
                connection,
                draft_id=draft.id,
                spec_document=spec_document,
                label=label,
                saved_config_id=saved_config_id,
                source_asset_id=source_asset_id,
                status=status,
                inspection_request=inspection_request,
                inspection=inspection,
                draft_request=draft_request,
                draft_result=draft_result,
                preview_request=None,
                preview=preview,
                timestamp=timestamp,
            )
            self._set_conversion_draft_current_revision(
                draft.id,
                revision.id,
                connection=connection,
                timestamp=timestamp,
            )
            if status == "saved":
                self._set_conversion_draft_confirmed_revision(
                    draft.id,
                    revision.id,
                    connection=connection,
                    timestamp=timestamp,
                )
                self._set_conversion_draft_saved_config(
                    draft.id,
                    saved_config_id,
                    connection=connection,
                    timestamp=timestamp,
                )
        return revision

    def list_conversion_drafts(
        self,
        *,
        status: DraftStatus | None = None,
        source_asset_selector: str | Path | None = None,
        saved_config_selector: str | None = None,
    ) -> list[ConversionDraftSummary]:
        where_clauses: list[str] = []
        params: list[str] = []
        if status is not None:
            where_clauses.append("status = ?")
            params.append(status)
        if source_asset_selector is not None:
            where_clauses.append("source_asset_id = ?")
            params.append(self.resolve_asset(source_asset_selector).id)
        if saved_config_selector is not None:
            where_clauses.append("saved_config_id = ?")
            params.append(self.resolve_saved_conversion_config(saved_config_selector).id)
        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM conversion_drafts
                {where_sql}
                ORDER BY updated_at DESC, id DESC
                """,
                params,
            ).fetchall()
        return [row_to_conversion_draft_summary(row) for row in rows]

    def get_conversion_draft(self, draft_id: str) -> ConversionDraft | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversion_drafts WHERE id = ?",
                (draft_id,),
            ).fetchone()
        if row is None:
            return None
        summary = row_to_conversion_draft_summary(row)
        return self._resolve_conversion_draft(summary, persist_migration=True)

    def resolve_conversion_draft(self, selector: str) -> ConversionDraft:
        draft = self.get_conversion_draft(selector)
        if draft is None:
            raise ConversionDraftNotFoundError(f"conversion draft not found: {selector}")
        return draft

    def list_conversion_draft_revisions(
        self,
        *,
        draft_selector: str | None = None,
        saved_config_selector: str | None = None,
        source_asset_selector: str | Path | None = None,
    ) -> list[ConversionDraftRevisionSummary]:
        where_clauses: list[str] = []
        params: list[str] = []
        if draft_selector is not None:
            where_clauses.append("draft_id = ?")
            params.append(self.resolve_conversion_draft(draft_selector).id)
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
                ORDER BY created_at DESC, revision_number DESC, id DESC
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
        revision_id: str,
    ) -> ConversionDraftRevision | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversion_draft_revisions WHERE id = ?",
                (revision_id,),
            ).fetchone()
        if row is None:
            return None
        summary = row_to_conversion_draft_revision_summary(
            row,
            document_path=str(self.paths.specs_dir / row["spec_document_path"]),
        )
        return self._resolve_conversion_draft_revision(summary, persist_migration=True)

    def inspect_asset(
        self,
        asset_selector: str | Path,
        *,
        request: InspectionRequest | dict[str, Any] | None = None,
    ) -> InspectionResult:
        inspection_request = _coerce_inspection_request(request)
        with self._open_asset_reader(asset_selector, operation="inspect") as (_asset, reader):
            try:
                return inspect_reader(
                    reader,
                    **inspection_request.model_dump(mode="python"),
                )
            except Exception as exc:
                raise AssetReadError(
                    f"failed to inspect asset {_asset.file_path}: {exc}"
                ) from exc

    def create_conversion_draft(
        self,
        asset_selector: str | Path,
        *,
        inspection_request: InspectionRequest | dict[str, Any] | None = None,
        draft_request: DraftSpecRequest | dict[str, Any] | None = None,
        label: str | None = None,
    ) -> ConversionDraft:
        resolved_inspection_request = _coerce_inspection_request(inspection_request)
        resolved_draft_request = _coerce_draft_request(draft_request)

        with self._open_asset_reader(asset_selector, operation="draft") as (asset, reader):
            try:
                inspection = inspect_reader(
                    reader,
                    **resolved_inspection_request.model_dump(mode="python"),
                )
            except Exception as exc:
                raise AssetReadError(
                    f"failed to inspect asset {asset.file_path}: {exc}"
                ) from exc
            draft_result = build_draft_conversion_spec(
                inspection,
                request=resolved_draft_request,
                reader=reader if resolved_draft_request.include_preview else None,
            )

        preview_request_payload: dict[str, Any] | None = None
        if draft_result.preview is not None:
            preview_request_payload = self._build_preview_request_payload(
                sample_n=resolved_draft_request.preview_rows,
                topic_type_hints=self._default_preview_topic_type_hints(draft_result.spec),
            )

        timestamp = _utc_now()
        with self._transaction() as connection:
            draft = self._create_conversion_draft(
                connection,
                source_asset_id=asset.id,
                status="draft",
                saved_config_id=None,
                timestamp=timestamp,
            )
            revision = self._append_conversion_draft_revision(
                connection,
                draft_id=draft.id,
                spec_document=draft_result.spec,
                label=label,
                saved_config_id=None,
                source_asset_id=asset.id,
                status="draft",
                inspection_request=resolved_inspection_request.model_dump(mode="python"),
                inspection=inspection.model_dump(mode="python"),
                draft_request=resolved_draft_request.model_dump(mode="python"),
                draft_result=_build_draft_result_payload(draft_result),
                preview_request=preview_request_payload,
                preview=draft_result.preview,
                timestamp=timestamp,
            )
            self._set_conversion_draft_current_revision(
                draft.id,
                revision.id,
                connection=connection,
                timestamp=timestamp,
            )

        return self.resolve_conversion_draft(draft.id)

    def update_conversion_draft(
        self,
        draft_selector: str,
        *,
        spec_document: ConversionSpecDocument | ConversionSpec | dict | str | Path,
        label: str | None = None,
    ) -> ConversionDraft:
        draft = self.resolve_conversion_draft(draft_selector)
        self._ensure_draft_is_mutable(draft, operation="update")
        current_revision = self._require_draft_current_revision(draft, operation="update")
        timestamp = _utc_now()

        with self._transaction() as connection:
            revision = self._append_conversion_draft_revision(
                connection,
                draft_id=draft.id,
                spec_document=spec_document,
                label=label,
                saved_config_id=draft.saved_config_id,
                source_asset_id=draft.source_asset_id or current_revision.source_asset_id,
                status="draft",
                inspection_request=current_revision.inspection_request_json,
                inspection=current_revision.inspection_json,
                draft_request=current_revision.draft_request_json,
                draft_result=current_revision.draft_result_json,
                preview_request=None,
                preview=None,
                timestamp=timestamp,
            )
            self._set_conversion_draft_current_revision(
                draft.id,
                revision.id,
                connection=connection,
                timestamp=timestamp,
            )
            if draft.confirmed_revision_id is not None:
                self._set_conversion_draft_confirmed_revision(
                    draft.id,
                    None,
                    connection=connection,
                    timestamp=timestamp,
                )
            self._set_conversion_draft_status(
                draft.id,
                "draft",
                connection=connection,
                timestamp=timestamp,
            )

        return self.resolve_conversion_draft(draft.id)

    def preview_conversion_draft(
        self,
        draft_selector: str,
        *,
        sample_n: int = 5,
        topic_type_hints: dict[str, str] | None = None,
        revision_selector: str | None = None,
    ) -> ConversionDraft:
        draft = self.resolve_conversion_draft(draft_selector)
        self._ensure_draft_is_mutable(draft, operation="preview")
        target_revision = self._resolve_draft_revision_for_draft(
            draft,
            revision_selector=revision_selector,
            operation="preview",
        )
        asset_id = draft.source_asset_id or target_revision.source_asset_id
        if asset_id is None:
            raise ConversionDraftStateError(
                f"draft {draft.id} does not have a source asset for preview"
            )

        effective_topic_type_hints = (
            dict(topic_type_hints)
            if topic_type_hints is not None
            else self._default_preview_topic_type_hints(target_revision.document.spec)
        )
        preview_request_payload = self._build_preview_request_payload(
            sample_n=sample_n,
            topic_type_hints=effective_topic_type_hints,
        )
        with self._open_asset_reader(asset_id, operation="preview") as (_asset, reader):
            preview = preview_conversion_spec(
                reader,
                target_revision.document.spec,
                sample_n=sample_n,
                topic_type_hints=effective_topic_type_hints or None,
            )

        self._update_conversion_draft_revision_preview(
            target_revision.id,
            preview_request=preview_request_payload,
            preview=preview,
        )
        return self.resolve_conversion_draft(draft.id)

    def confirm_conversion_draft(
        self,
        draft_selector: str,
        *,
        revision_selector: str | None = None,
    ) -> ConversionDraft:
        draft = self.resolve_conversion_draft(draft_selector)
        self._ensure_draft_is_mutable(draft, operation="confirm")
        current_revision = self._require_draft_current_revision(draft, operation="confirm")
        target_revision = self._resolve_draft_revision_for_draft(
            draft,
            revision_selector=revision_selector,
            operation="confirm",
        )
        if target_revision.id != current_revision.id:
            raise ConversionDraftConfirmationError(
                f"only the current revision of draft {draft.id} can be confirmed"
            )
        if target_revision.preview_json is None:
            raise ConversionDraftConfirmationError(
                f"draft {draft.id} revision {target_revision.id} must be previewed before confirmation"
            )

        preview = PreviewResult.model_validate(target_revision.preview_json)
        if not preview.preflight_ok:
            raise ConversionDraftConfirmationError(
                "draft "
                f"{draft.id} revision {target_revision.id} cannot be confirmed because preview "
                f"reported {preview.bad_records} bad record(s)"
            )

        timestamp = _utc_now()
        with self._transaction() as connection:
            self._set_conversion_draft_confirmed_revision(
                draft.id,
                target_revision.id,
                connection=connection,
                timestamp=timestamp,
            )
            self._set_conversion_draft_status(
                draft.id,
                "confirmed",
                connection=connection,
                timestamp=timestamp,
            )

        return self.resolve_conversion_draft(draft.id)

    def discard_conversion_draft(
        self,
        draft_selector: str,
    ) -> ConversionDraft:
        draft = self.resolve_conversion_draft(draft_selector)
        self._ensure_draft_is_mutable(draft, operation="discard")
        self._set_conversion_draft_status(draft.id, "discarded")
        return self.resolve_conversion_draft(draft.id)

    def save_conversion_config_from_draft(
        self,
        draft_selector: str,
        *,
        name: str,
        description: str | None = None,
    ) -> SavedConversionConfig:
        draft = self.resolve_conversion_draft(draft_selector)
        if draft.status != "confirmed":
            raise ConversionDraftConfirmationError(
                f"draft {draft.id} must be confirmed before it can be saved as a config"
            )

        confirmed_revision = draft.confirmed_revision
        if confirmed_revision is None:
            raise ConversionDraftConfirmationError(
                f"draft {draft.id} does not have a confirmed revision to save"
            )

        timestamp = _utc_now()
        promoted_document = self._build_saved_config_document_from_draft(
            draft,
            confirmed_revision,
        )
        with self._transaction() as connection:
            config = self._insert_saved_conversion_config(
                connection,
                name=name,
                spec_document=promoted_document,
                description=description,
                timestamp=timestamp,
            )
            self._set_conversion_draft_revision_saved_config(
                confirmed_revision.id,
                saved_config_id=config.id,
                status="saved",
                connection=connection,
                timestamp=timestamp,
            )
            self._set_conversion_draft_saved_config(
                draft.id,
                config.id,
                connection=connection,
                timestamp=timestamp,
            )
            self._set_conversion_draft_status(
                draft.id,
                "saved",
                connection=connection,
                timestamp=timestamp,
            )

        return config

    @contextmanager
    def _open_asset_reader(
        self,
        asset_selector: str | Path,
        *,
        operation: str,
    ) -> Iterator[tuple[Any, Any]]:
        asset = self.resolve_asset(asset_selector)
        asset_path = self._require_asset_file_path(asset, operation=operation)
        try:
            reader = RosReader.open(asset_path)
        except Exception as exc:
            raise AssetReadError(
                f"failed to open source asset for {operation}: {asset_path}: {exc}"
            ) from exc
        try:
            yield asset, reader
        finally:
            try:
                reader.close()
            except Exception:
                pass

    def _ensure_draft_is_mutable(
        self,
        draft: ConversionDraft,
        *,
        operation: str,
    ) -> None:
        if draft.status == "saved":
            raise ConversionDraftStateError(
                f"cannot {operation} draft {draft.id} after it has been saved"
            )
        if draft.status == "discarded":
            raise ConversionDraftStateError(
                f"cannot {operation} draft {draft.id} after it has been discarded"
            )

    def _require_draft_current_revision(
        self,
        draft: ConversionDraft,
        *,
        operation: str,
    ) -> ConversionDraftRevision:
        if draft.current_revision is None:
            raise ConversionDraftStateError(
                f"cannot {operation} draft {draft.id} because it has no current revision"
            )
        return draft.current_revision

    def _resolve_draft_revision_for_draft(
        self,
        draft: ConversionDraft,
        *,
        revision_selector: str | None,
        operation: str,
    ) -> ConversionDraftRevision:
        if revision_selector is None:
            return self._require_draft_current_revision(draft, operation=operation)
        revision = self.get_conversion_draft_revision(revision_selector)
        if revision is None:
            raise ConversionDraftRevisionNotFoundError(
                f"conversion draft revision not found: {revision_selector}"
            )
        if revision.draft_id != draft.id:
            raise ConversionDraftStateError(
                f"revision {revision_selector} does not belong to draft {draft.id}"
            )
        return revision

    def _default_preview_topic_type_hints(
        self,
        spec: ConversionSpec,
    ) -> dict[str, str]:
        if spec.decoding is None:
            return {}
        return {
            topic: topic_spec.type_hint
            for topic, topic_spec in spec.decoding.topics.items()
            if topic_spec.type_hint is not None
        }

    def _build_preview_request_payload(
        self,
        *,
        sample_n: int,
        topic_type_hints: dict[str, str] | None,
    ) -> dict[str, Any]:
        return {
            "sample_n": sample_n,
            "topic_type_hints": dict(topic_type_hints or {}),
        }

    def _build_saved_config_document_from_draft(
        self,
        draft: ConversionDraft,
        confirmed_revision: ConversionDraftRevision,
    ) -> ConversionSpecDocument:
        metadata = dict(confirmed_revision.document.metadata)
        workspace_metadata = metadata.get("hephaes_workspace")
        if not isinstance(workspace_metadata, dict):
            workspace_metadata = {}
        else:
            workspace_metadata = dict(workspace_metadata)
        workspace_metadata["draft_promotion"] = {
            "draft_id": draft.id,
            "confirmed_revision_id": confirmed_revision.id,
            "source_asset_id": draft.source_asset_id,
            "preview_request": dict(confirmed_revision.preview_request_json),
            "preview": (
                dict(confirmed_revision.preview_json)
                if confirmed_revision.preview_json is not None
                else None
            ),
        }
        metadata["hephaes_workspace"] = workspace_metadata
        return confirmed_revision.document.model_copy(
            deep=True,
            update={"metadata": metadata},
        )

    def _resolve_conversion_draft(
        self,
        summary: ConversionDraftSummary,
        *,
        persist_migration: bool,
    ) -> ConversionDraft:
        current_revision: ConversionDraftRevision | None = None
        if summary.current_revision_id is not None:
            current_revision = self.get_conversion_draft_revision(summary.current_revision_id)
            if current_revision is None:
                raise ConversionDraftStateError(
                    f"draft {summary.id} is missing current revision {summary.current_revision_id}"
                )

        confirmed_revision: ConversionDraftRevision | None = None
        if summary.confirmed_revision_id is not None:
            if summary.confirmed_revision_id == summary.current_revision_id:
                confirmed_revision = current_revision
            else:
                confirmed_revision = self.get_conversion_draft_revision(
                    summary.confirmed_revision_id
                )
            if confirmed_revision is None:
                raise ConversionDraftStateError(
                    "draft "
                    f"{summary.id} is missing confirmed revision {summary.confirmed_revision_id}"
                )

        if persist_migration:
            summary = self._get_conversion_draft_summary_or_raise(summary.id)

        return build_conversion_draft(
            summary,
            current_revision=current_revision,
            confirmed_revision=confirmed_revision,
        )

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

    def _create_conversion_draft(
        self,
        connection: sqlite3.Connection,
        *,
        source_asset_id: str | None,
        status: DraftStatus,
        saved_config_id: str | None,
        timestamp,
        draft_id: str | None = None,
    ) -> ConversionDraftSummary:
        draft_id = draft_id or str(uuid4())
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
                draft_id,
                source_asset_id,
                status,
                None,
                None,
                saved_config_id,
                to_db_timestamp(timestamp),
                to_db_timestamp(timestamp),
                to_db_timestamp(timestamp) if status == "discarded" else None,
            ),
        )
        row = connection.execute(
            "SELECT * FROM conversion_drafts WHERE id = ?",
            (draft_id,),
        ).fetchone()
        assert row is not None
        return row_to_conversion_draft_summary(row)

    def _append_conversion_draft_revision(
        self,
        connection: sqlite3.Connection,
        *,
        draft_id: str,
        spec_document: ConversionSpecDocument | ConversionSpec | dict | str | Path,
        label: str | None,
        saved_config_id: str | None,
        source_asset_id: str | None,
        status: RevisionStatus,
        inspection_request: dict[str, Any] | Any | None,
        inspection: dict[str, Any] | Any | None,
        draft_request: dict[str, Any] | Any | None,
        draft_result: dict[str, Any] | Any | None,
        preview_request: dict[str, Any] | Any | None,
        preview: dict[str, Any] | Any | None,
        timestamp,
        revision_id: str | None = None,
        revision_number: int | None = None,
    ) -> ConversionDraftRevision:
        document = _load_conversion_document_input(spec_document)
        revision_id = revision_id or str(uuid4())
        preview_payload = _json_safe_optional_payload(preview)
        if revision_number is None:
            row = connection.execute(
                """
                SELECT COALESCE(MAX(revision_number), 0) AS max_revision_number
                FROM conversion_draft_revisions
                WHERE draft_id = ?
                """,
                (draft_id,),
            ).fetchone()
            revision_number = int(row["max_revision_number"]) + 1

        relative_document_path = _build_draft_revision_relative_path(revision_id)
        document_path = self.paths.specs_dir / relative_document_path
        _write_text_atomically(
            document_path,
            dump_conversion_spec_document(document, format="json"),
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
                draft_id,
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
                json.dumps(_json_safe_payload(preview_request)),
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
        assert row is not None
        summary = row_to_conversion_draft_revision_summary(
            row,
            document_path=str(document_path),
        )
        return build_conversion_draft_revision(summary, document=document)

    def _set_conversion_draft_status(
        self,
        draft_id: str,
        status: DraftStatus,
        *,
        connection: sqlite3.Connection | None = None,
        timestamp=None,
    ) -> None:
        timestamp = timestamp or _utc_now()
        if connection is None:
            with self._transaction() as connection:
                self._set_conversion_draft_status(
                    draft_id,
                    status,
                    connection=connection,
                    timestamp=timestamp,
                )
            return

        draft = self._get_conversion_draft_summary_or_raise(
            draft_id,
            connection=connection,
        )
        allowed_transitions: dict[DraftStatus, set[DraftStatus]] = {
            "draft": {"draft", "confirmed", "discarded", "saved"},
            "confirmed": {"confirmed", "draft", "discarded", "saved"},
            "saved": {"saved"},
            "discarded": {"discarded"},
        }
        if status not in allowed_transitions[draft.status]:
            raise ConversionDraftStateError(
                f"cannot transition draft {draft_id} from {draft.status} to {status}"
            )
        connection.execute(
            """
            UPDATE conversion_drafts
            SET status = ?, updated_at = ?, discarded_at = ?
            WHERE id = ?
            """,
            (
                status,
                to_db_timestamp(timestamp),
                to_db_timestamp(timestamp) if status == "discarded" else None,
                draft_id,
            ),
        )

    def _set_conversion_draft_current_revision(
        self,
        draft_id: str,
        revision_id: str,
        *,
        connection: sqlite3.Connection | None = None,
        timestamp=None,
    ) -> None:
        timestamp = timestamp or _utc_now()
        if connection is None:
            with self._transaction() as connection:
                self._set_conversion_draft_current_revision(
                    draft_id,
                    revision_id,
                    connection=connection,
                    timestamp=timestamp,
                )
            return

        revision = self._get_conversion_draft_revision_summary_or_raise(
            revision_id,
            connection=connection,
        )
        if revision.draft_id != draft_id:
            raise ConversionDraftStateError(
                f"revision {revision_id} does not belong to draft {draft_id}"
            )
        connection.execute(
            """
            UPDATE conversion_drafts
            SET current_revision_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                revision_id,
                to_db_timestamp(timestamp),
                draft_id,
            ),
        )

    def _set_conversion_draft_confirmed_revision(
        self,
        draft_id: str,
        revision_id: str | None,
        *,
        connection: sqlite3.Connection | None = None,
        timestamp=None,
    ) -> None:
        timestamp = timestamp or _utc_now()
        if connection is None:
            with self._transaction() as connection:
                self._set_conversion_draft_confirmed_revision(
                    draft_id,
                    revision_id,
                    connection=connection,
                    timestamp=timestamp,
                )
            return

        if revision_id is not None:
            revision = self._get_conversion_draft_revision_summary_or_raise(
                revision_id,
                connection=connection,
            )
            if revision.draft_id != draft_id:
                raise ConversionDraftStateError(
                    f"revision {revision_id} does not belong to draft {draft_id}"
                )
        connection.execute(
            """
            UPDATE conversion_drafts
            SET confirmed_revision_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                revision_id,
                to_db_timestamp(timestamp),
                draft_id,
            ),
        )

    def _set_conversion_draft_saved_config(
        self,
        draft_id: str,
        saved_config_id: str | None,
        *,
        connection: sqlite3.Connection | None = None,
        timestamp=None,
    ) -> None:
        timestamp = timestamp or _utc_now()
        if connection is None:
            with self._transaction() as connection:
                self._set_conversion_draft_saved_config(
                    draft_id,
                    saved_config_id,
                    connection=connection,
                    timestamp=timestamp,
                )
            return

        connection.execute(
            """
            UPDATE conversion_drafts
            SET saved_config_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                saved_config_id,
                to_db_timestamp(timestamp),
                draft_id,
            ),
        )

    def _set_conversion_draft_revision_saved_config(
        self,
        revision_id: str,
        *,
        saved_config_id: str | None,
        status: RevisionStatus | None = None,
        connection: sqlite3.Connection | None = None,
        timestamp=None,
    ) -> None:
        timestamp = timestamp or _utc_now()
        if connection is None:
            with self._transaction() as connection:
                self._set_conversion_draft_revision_saved_config(
                    revision_id,
                    saved_config_id=saved_config_id,
                    status=status,
                    connection=connection,
                    timestamp=timestamp,
                )
            return

        revision = self._get_conversion_draft_revision_summary_or_raise(
            revision_id,
            connection=connection,
        )
        connection.execute(
            """
            UPDATE conversion_draft_revisions
            SET saved_config_id = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                saved_config_id,
                status or revision.status,
                to_db_timestamp(timestamp),
                revision_id,
            ),
        )

    def _get_conversion_draft_summary_or_raise(
        self,
        draft_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> ConversionDraftSummary:
        if connection is not None:
            row = connection.execute(
                "SELECT * FROM conversion_drafts WHERE id = ?",
                (draft_id,),
            ).fetchone()
        else:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM conversion_drafts WHERE id = ?",
                    (draft_id,),
                ).fetchone()
        if row is None:
            raise ConversionDraftNotFoundError(f"conversion draft not found: {draft_id}")
        return row_to_conversion_draft_summary(row)

    def _get_conversion_draft_revision_summary_or_raise(
        self,
        revision_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> ConversionDraftRevisionSummary:
        if connection is not None:
            row = connection.execute(
                "SELECT * FROM conversion_draft_revisions WHERE id = ?",
                (revision_id,),
            ).fetchone()
        else:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM conversion_draft_revisions WHERE id = ?",
                    (revision_id,),
                ).fetchone()
        if row is None:
            raise ConversionDraftRevisionNotFoundError(
                f"conversion draft revision not found: {revision_id}"
            )
        return row_to_conversion_draft_revision_summary(
            row,
            document_path=str(self.paths.specs_dir / row["spec_document_path"]),
        )

    def _update_conversion_draft_revision_preview(
        self,
        revision_id: str,
        *,
        preview_request: dict[str, Any] | Any | None,
        preview: dict[str, Any] | Any | None,
        connection: sqlite3.Connection | None = None,
        timestamp=None,
    ) -> None:
        timestamp = timestamp or _utc_now()
        if connection is None:
            with self._transaction() as connection:
                self._update_conversion_draft_revision_preview(
                    revision_id,
                    preview_request=preview_request,
                    preview=preview,
                    connection=connection,
                    timestamp=timestamp,
                )
            return

        self._get_conversion_draft_revision_summary_or_raise(
            revision_id,
            connection=connection,
        )
        preview_payload = _json_safe_optional_payload(preview)
        connection.execute(
            """
            UPDATE conversion_draft_revisions
            SET preview_request_json = ?, preview_json = ?, invalid_reason = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                json.dumps(_json_safe_payload(preview_request)),
                json.dumps(preview_payload) if preview_payload is not None else None,
                None,
                to_db_timestamp(timestamp),
                revision_id,
            ),
        )

    def _update_conversion_draft_revision_invalid_reason(
        self,
        revision_id: str,
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
                    revision_id,
                ),
            )

    def _update_conversion_draft_revision_metadata(
        self,
        revision_id: str,
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
                    revision_id,
                ),
            )
