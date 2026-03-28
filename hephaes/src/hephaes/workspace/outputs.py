from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from .errors import OutputArtifactNotFoundError, WorkspaceError
from .models import OutputArtifact, OutputArtifactSummary
from .serialization import row_to_output_artifact, row_to_output_artifact_summary, to_db_timestamp
from .utils import (
    _infer_media_type,
    _infer_output_format_and_role,
    _relative_output_path,
    _summarize_output_metadata,
    _utc_now,
)


class WorkspaceOutputMixin:
    def register_output_artifacts(
        self,
        *,
        output_root: str | Path,
        paths: list[str | Path] | None = None,
        conversion_run_id: str | None = None,
        source_asset_id: str | None = None,
        source_asset_path: str | None = None,
        saved_config_id: str | None = None,
    ) -> list[OutputArtifact]:
        root = Path(output_root).expanduser().resolve(strict=False)
        if not root.exists():
            raise WorkspaceError(f"output path does not exist: {root}")

        if paths is not None:
            candidate_paths = sorted(
                {
                    Path(candidate_path).expanduser().resolve(strict=False)
                    for candidate_path in paths
                }
            )
            output_root_path = root if root.is_dir() else root.parent
        elif root.is_file():
            candidate_paths = [root]
            output_root_path = root.parent
        else:
            candidate_paths = [path for path in sorted(root.rglob("*")) if path.is_file()]
            output_root_path = root

        timestamp = _utc_now()
        registered_paths: list[str] = []

        with self._transaction() as connection:
            for artifact_path in candidate_paths:
                output_path = str(artifact_path)
                format_name, role = _infer_output_format_and_role(artifact_path)
                manifest_available = int(
                    role == "manifest" or artifact_path.with_suffix(".manifest.json").exists()
                )
                report_available = int(
                    artifact_path.with_name(f"{artifact_path.stem}.report.md").exists()
                )
                metadata = _summarize_output_metadata(
                    artifact_path,
                    format_name=format_name,
                    role=role,
                )
                existing = connection.execute(
                    "SELECT id, created_at FROM output_artifacts WHERE output_path = ?",
                    (output_path,),
                ).fetchone()
                artifact_id = existing["id"] if existing is not None else str(uuid4())
                created_at = (
                    existing["created_at"] if existing is not None else to_db_timestamp(timestamp)
                )
                connection.execute(
                    """
                    INSERT INTO output_artifacts(
                        id,
                        conversion_run_id,
                        source_asset_id,
                        source_asset_path,
                        saved_config_id,
                        output_path,
                        relative_path,
                        file_name,
                        format,
                        role,
                        media_type,
                        size_bytes,
                        availability_status,
                        manifest_available,
                        report_available,
                        metadata_json,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(output_path) DO UPDATE SET
                        conversion_run_id = excluded.conversion_run_id,
                        source_asset_id = excluded.source_asset_id,
                        source_asset_path = excluded.source_asset_path,
                        saved_config_id = excluded.saved_config_id,
                        relative_path = excluded.relative_path,
                        file_name = excluded.file_name,
                        format = excluded.format,
                        role = excluded.role,
                        media_type = excluded.media_type,
                        size_bytes = excluded.size_bytes,
                        availability_status = excluded.availability_status,
                        manifest_available = excluded.manifest_available,
                        report_available = excluded.report_available,
                        metadata_json = excluded.metadata_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        artifact_id,
                        conversion_run_id,
                        source_asset_id,
                        source_asset_path,
                        saved_config_id,
                        output_path,
                        _relative_output_path(output_root_path, artifact_path),
                        artifact_path.name,
                        format_name,
                        role,
                        _infer_media_type(artifact_path, format_name),
                        artifact_path.stat().st_size,
                        "ready",
                        manifest_available,
                        report_available,
                        json.dumps(metadata),
                        created_at,
                        to_db_timestamp(timestamp),
                    ),
                )
                registered_paths.append(output_path)

            if conversion_run_id is not None and paths is None:
                registered_path_set = set(registered_paths)
                missing_rows = connection.execute(
                    """
                    SELECT id
                    FROM output_artifacts
                    WHERE conversion_run_id = ? AND output_path NOT IN (
                        SELECT value FROM json_each(?)
                    )
                    """,
                    (conversion_run_id, json.dumps(sorted(registered_path_set))),
                ).fetchall()
                for row in missing_rows:
                    connection.execute(
                        """
                        UPDATE output_artifacts
                        SET availability_status = ?, size_bytes = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            "missing",
                            0,
                            to_db_timestamp(timestamp),
                            row["id"],
                        ),
                    )

        return [self.get_output_artifact_or_raise_by_path(path) for path in registered_paths]

    def list_output_artifacts(self) -> list[OutputArtifactSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM output_artifacts
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        return [row_to_output_artifact_summary(row) for row in rows]

    def get_output_artifact(self, output_id: str) -> OutputArtifact | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM output_artifacts WHERE id = ?",
                (output_id,),
            ).fetchone()
        if row is None:
            return None
        return row_to_output_artifact(row)

    def get_output_artifact_or_raise(self, output_id: str) -> OutputArtifact:
        artifact = self.get_output_artifact(output_id)
        if artifact is None:
            raise OutputArtifactNotFoundError(f"output artifact not found: {output_id}")
        return artifact

    def get_output_artifact_or_raise_by_path(self, output_path: str) -> OutputArtifact:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM output_artifacts WHERE output_path = ?",
                (output_path,),
            ).fetchone()
        if row is None:
            raise OutputArtifactNotFoundError(f"output artifact not found: {output_path}")
        return row_to_output_artifact(row)
