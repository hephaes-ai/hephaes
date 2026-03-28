from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from ..conversion.spec_io import (
    ConversionSpecDocument,
    build_conversion_spec_document,
    load_conversion_spec_document,
)
from ..models import ConversionSpec
from .errors import AssetNotFoundError, WorkspaceError
from .models import ConversionRun, OutputArtifact, SavedConversionConfig
from .serialization import row_to_conversion_run, to_db_timestamp
from .utils import _inspect_asset_path, _utc_now


class WorkspaceConversionMixin:
    def create_conversion_run(
        self,
        *,
        source_asset_ids: list[str] | None,
        source_asset_paths: list[str],
        output_dir: str | Path,
        saved_config_id: str | None = None,
        saved_config_revision_id: str | None = None,
        config: dict | None = None,
        job_id: str | None = None,
        run_id: str | None = None,
    ) -> ConversionRun:
        timestamp = _utc_now()
        run_id = run_id or str(uuid4())
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO conversion_runs(
                    id,
                    job_id,
                    status,
                    source_asset_ids_json,
                    source_asset_paths_json,
                    saved_config_id,
                    saved_config_revision_id,
                    config_json,
                    output_dir,
                    output_paths_json,
                    error_message,
                    created_at,
                    updated_at,
                    started_at,
                    completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    job_id,
                    "pending",
                    json.dumps(source_asset_ids or []),
                    json.dumps(source_asset_paths),
                    saved_config_id,
                    saved_config_revision_id,
                    json.dumps(config or {}),
                    str(Path(output_dir).expanduser().resolve(strict=False)),
                    json.dumps([]),
                    None,
                    to_db_timestamp(timestamp),
                    to_db_timestamp(timestamp),
                    None,
                    None,
                ),
            )
            if job_id is not None:
                connection.execute(
                    "UPDATE jobs SET conversion_run_id = ?, updated_at = ? WHERE id = ?",
                    (run_id, to_db_timestamp(timestamp), job_id),
                )
        return self.get_conversion_run_or_raise(run_id)

    def list_conversion_runs(self) -> list[ConversionRun]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM conversion_runs
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        return [row_to_conversion_run(row) for row in rows]

    def get_conversion_run(self, run_id: str) -> ConversionRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversion_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return row_to_conversion_run(row)

    def get_conversion_run_or_raise(self, run_id: str) -> ConversionRun:
        run = self.get_conversion_run(run_id)
        if run is None:
            raise WorkspaceError(f"conversion run not found: {run_id}")
        return run

    def mark_conversion_run_running(self, run_id: str) -> ConversionRun:
        timestamp = _utc_now()
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE conversion_runs
                SET status = 'running', updated_at = ?, started_at = COALESCE(started_at, ?)
                WHERE id = ?
                """,
                (
                    to_db_timestamp(timestamp),
                    to_db_timestamp(timestamp),
                    run_id,
                ),
            )
        return self.get_conversion_run_or_raise(run_id)

    def mark_conversion_run_succeeded(
        self,
        run_id: str,
        *,
        output_paths: list[str],
    ) -> ConversionRun:
        timestamp = _utc_now()
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE conversion_runs
                SET status = 'succeeded', output_paths_json = ?, error_message = NULL,
                    updated_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(output_paths),
                    to_db_timestamp(timestamp),
                    to_db_timestamp(timestamp),
                    run_id,
                ),
            )
        return self.get_conversion_run_or_raise(run_id)

    def mark_conversion_run_failed(self, run_id: str, *, error_message: str) -> ConversionRun:
        timestamp = _utc_now()
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE conversion_runs
                SET status = 'failed', error_message = ?, updated_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    error_message,
                    to_db_timestamp(timestamp),
                    to_db_timestamp(timestamp),
                    run_id,
                ),
            )
        return self.get_conversion_run_or_raise(run_id)

    def run_conversion(
        self,
        source: str | Path,
        *,
        saved_config_selector: str | None = None,
        spec_document: ConversionSpecDocument | ConversionSpec | dict | str | Path | None = None,
        output_dir: str | Path | None = None,
        max_workers: int = 1,
    ) -> list[OutputArtifact]:
        from . import Converter as WorkspaceConverter

        if max_workers < 1:
            raise WorkspaceError("--max-workers must be >= 1")
        if (saved_config_selector is None) == (spec_document is None):
            raise WorkspaceError(
                "provide exactly one of saved_config_selector or spec_document"
            )

        registered_asset = None
        try:
            registered_asset = self.resolve_asset(source)
            source_path = Path(registered_asset.file_path)
        except AssetNotFoundError:
            source_path, _file_type, _file_size = _inspect_asset_path(source)

        saved_config: SavedConversionConfig | None = None
        saved_config_revision_id: str | None = None
        if saved_config_selector is not None:
            saved_config = self.resolve_saved_conversion_config(saved_config_selector)
            saved_config_revision_id = self._latest_saved_conversion_config_revision_id(
                saved_config.id
            )
            document = saved_config.document
        else:
            if spec_document is None:
                raise WorkspaceError("spec document is required")
            if isinstance(spec_document, ConversionSpec):
                document = build_conversion_spec_document(spec_document)
            else:
                document = load_conversion_spec_document(spec_document)

        resolved_output_dir = (
            Path(output_dir).expanduser().resolve(strict=False)
            if output_dir is not None
            else self.paths.outputs_dir / str(uuid4())
        )
        resolved_output_dir.mkdir(parents=True, exist_ok=True)

        source_asset_ids = [registered_asset.id] if registered_asset is not None else []
        source_asset_paths = [
            registered_asset.file_path if registered_asset is not None else str(source_path)
        ]
        config_snapshot = {
            "saved_config_id": saved_config.id if saved_config is not None else None,
            "saved_config_name": saved_config.name if saved_config is not None else None,
            "saved_config_revision_id": saved_config_revision_id,
            "spec_schema": {
                "name": document.spec.schema.name,
                "version": document.spec.schema.version,
            },
            "output_format": document.spec.output.format,
            "max_workers": max_workers,
        }
        job = self.create_job(
            kind="conversion",
            target_asset_ids=source_asset_ids,
            config=config_snapshot,
        )
        run = self.create_conversion_run(
            source_asset_ids=source_asset_ids,
            source_asset_paths=source_asset_paths,
            output_dir=resolved_output_dir,
            saved_config_id=saved_config.id if saved_config is not None else None,
            saved_config_revision_id=saved_config_revision_id,
            config=config_snapshot,
            job_id=job.id,
        )
        self.mark_job_running(job.id)
        self.mark_conversion_run_running(run.id)

        try:
            converter = WorkspaceConverter(
                [str(source_path)],
                None,
                resolved_output_dir,
                spec=document.spec,
                max_workers=max_workers,
            )
            dataset_paths = converter.convert()

            artifact_paths: list[Path] = []
            for dataset_path in dataset_paths:
                artifact_paths.append(dataset_path)
                manifest_path = dataset_path.with_suffix(".manifest.json")
                report_path = dataset_path.with_name(f"{dataset_path.stem}.report.md")
                if manifest_path.exists():
                    artifact_paths.append(manifest_path)
                if report_path.exists():
                    artifact_paths.append(report_path)

            outputs = self.register_output_artifacts(
                output_root=resolved_output_dir,
                paths=[str(path) for path in artifact_paths],
                conversion_run_id=run.id,
                source_asset_id=registered_asset.id if registered_asset is not None else None,
                source_asset_path=(
                    registered_asset.file_path if registered_asset is not None else str(source_path)
                ),
                saved_config_id=saved_config.id if saved_config is not None else None,
            )
            self.mark_conversion_run_succeeded(
                run.id,
                output_paths=[output.output_path for output in outputs],
            )
            self.mark_job_succeeded(job.id, conversion_run_id=run.id)
            return outputs
        except Exception as exc:
            self.mark_conversion_run_failed(run.id, error_message=str(exc))
            self.mark_job_failed(job.id, error_message=str(exc))
            raise
