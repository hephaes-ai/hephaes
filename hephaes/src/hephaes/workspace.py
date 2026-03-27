from __future__ import annotations

import json
import mimetypes
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from ._workspace_indexing import build_index_metadata_payload, profile_asset_file
from ._workspace_models import (
    AssetRegistrationMode,
    DefaultEpisodeSummary,
    IndexedAssetMetadata,
    IndexedTopicSummary,
    OutputArtifact,
    OutputArtifactSummary,
    RegisteredAsset,
    SavedConversionConfig,
    SavedConversionConfigSummary,
    SourceAssetMetadata,
    VisualizationSummary,
    WorkspacePaths,
)
from ._workspace_schema import (
    WORKSPACE_DB_FILENAME,
    WORKSPACE_DIRNAME,
    WORKSPACE_SCHEMA_VERSION,
    initialize_workspace_schema,
    migrate_workspace_schema,
)
from ._workspace_serialization import (
    build_saved_conversion_config,
    from_db_timestamp,
    row_to_indexed_asset_metadata,
    row_to_output_artifact,
    row_to_output_artifact_summary,
    row_to_registered_asset,
    row_to_saved_conversion_config_summary,
    to_db_timestamp,
    upsert_asset_metadata,
)
from .conversion.spec_io import (
    CONVERSION_SPEC_DOCUMENT_VERSION,
    ConversionSpecDocument,
    build_conversion_spec_document,
    dump_conversion_spec_document,
    load_conversion_spec_document,
    migrate_conversion_spec_document,
)
from .converter import Converter
from .models import ConversionSpec

SUPPORTED_ASSET_FILE_TYPES = frozenset({"bag", "mcap"})


class WorkspaceError(Exception):
    """Base exception for workspace operations."""


class WorkspaceNotFoundError(WorkspaceError):
    """Raised when no workspace can be resolved for the requested path."""


class WorkspaceAlreadyExistsError(WorkspaceError):
    """Raised when attempting to initialize an existing workspace."""


class InvalidAssetPathError(WorkspaceError):
    """Raised when a requested asset path does not point to a supported local file."""


class AssetAlreadyRegisteredError(WorkspaceError):
    """Raised when a requested asset path already exists in the workspace."""


class AssetNotFoundError(WorkspaceError):
    """Raised when a requested asset cannot be found in the workspace."""


class ConversionConfigAlreadyExistsError(WorkspaceError):
    """Raised when a saved conversion config name already exists."""


class ConversionConfigNotFoundError(WorkspaceError):
    """Raised when a saved conversion config cannot be found."""


class ConversionConfigInvalidError(WorkspaceError):
    """Raised when a saved conversion config document cannot be loaded."""


class OutputArtifactNotFoundError(WorkspaceError):
    """Raised when a tracked output artifact cannot be found."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_root(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _normalize_asset_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _infer_asset_file_type(path: Path) -> str:
    suffix = path.suffix.strip().lower()
    if suffix.startswith("."):
        suffix = suffix[1:]
    return suffix or "unknown"


def _inspect_asset_path(path: str | Path) -> tuple[Path, str, int]:
    normalized = _normalize_asset_path(path)
    if not normalized.exists():
        raise InvalidAssetPathError(f"asset path does not exist: {normalized}")
    if not normalized.is_file():
        raise InvalidAssetPathError(f"asset path is not a file: {normalized}")

    file_type = _infer_asset_file_type(normalized)
    if file_type not in SUPPORTED_ASSET_FILE_TYPES:
        supported_types = ", ".join(sorted(SUPPORTED_ASSET_FILE_TYPES))
        raise InvalidAssetPathError(
            f"unsupported asset type: {normalized.name} (supported: {supported_types})"
        )

    return normalized, file_type, normalized.stat().st_size


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _write_text_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


def _infer_output_format_and_role(path: Path) -> tuple[str, str]:
    name = path.name.lower()
    if name.endswith(".manifest.json"):
        return "json", "manifest"
    if name.endswith(".report.md"):
        return "md", "report"
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return "parquet", "dataset"
    if suffix == ".tfrecord":
        return "tfrecord", "dataset"
    if suffix == ".jsonl":
        return "jsonl", "sidecar"
    if suffix == ".json":
        return "json", "sidecar"
    return suffix.lstrip(".") or "unknown", "sidecar"


def _infer_media_type(path: Path, format_name: str) -> str | None:
    if format_name == "parquet":
        return "application/x-parquet"
    if format_name == "tfrecord":
        return "application/octet-stream"
    if format_name == "json":
        return "application/json"
    if format_name == "jsonl":
        return "application/x-ndjson"
    return mimetypes.guess_type(path.name)[0]


def _load_json_file(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _summarize_output_metadata(path: Path, *, format_name: str, role: str) -> dict:
    metadata: dict = {}
    if role == "manifest":
        payload = _load_json_file(path)
        if payload is not None:
            metadata["manifest"] = payload
        return metadata

    manifest_path = path.with_suffix(".manifest.json")
    if manifest_path.exists():
        manifest_payload = _load_json_file(manifest_path)
        if manifest_payload is not None:
            metadata["manifest"] = manifest_payload
    return metadata


def _relative_output_path(output_root: Path, artifact_path: Path) -> str:
    try:
        return str(artifact_path.relative_to(output_root))
    except ValueError:
        return artifact_path.name


class Workspace:
    """Package-owned local workspace for persistent Hephaes state."""

    def __init__(self, paths: WorkspacePaths) -> None:
        self.paths = paths

    @property
    def root(self) -> Path:
        return self.paths.root

    @property
    def workspace_dir(self) -> Path:
        return self.paths.workspace_dir

    @property
    def database_path(self) -> Path:
        return self.paths.database_path

    @classmethod
    def init(cls, root: str | Path, *, exist_ok: bool = False) -> "Workspace":
        normalized_root = _normalize_root(root)
        workspace_dir = normalized_root / WORKSPACE_DIRNAME
        if workspace_dir.exists() and not exist_ok:
            raise WorkspaceAlreadyExistsError(
                f"workspace already exists at {workspace_dir}"
            )

        paths = WorkspacePaths(
            root=normalized_root,
            workspace_dir=workspace_dir,
            database_path=workspace_dir / WORKSPACE_DB_FILENAME,
            outputs_dir=workspace_dir / "outputs",
            specs_dir=workspace_dir / "specs",
            jobs_dir=workspace_dir / "jobs",
        )
        cls._create_layout(paths)
        workspace = cls(paths)
        workspace._initialize_database()
        return workspace

    @classmethod
    def open(cls, root: str | Path | None = None) -> "Workspace":
        start_path = _normalize_root(root or Path.cwd())
        workspace_dir = cls._find_workspace_dir(start_path)
        paths = WorkspacePaths(
            root=workspace_dir.parent,
            workspace_dir=workspace_dir,
            database_path=workspace_dir / WORKSPACE_DB_FILENAME,
            outputs_dir=workspace_dir / "outputs",
            specs_dir=workspace_dir / "specs",
            jobs_dir=workspace_dir / "jobs",
        )
        workspace = cls(paths)
        workspace._validate_database()
        return workspace

    @staticmethod
    def _find_workspace_dir(start_path: Path) -> Path:
        current = start_path if start_path.is_dir() else start_path.parent
        for candidate in (current, *current.parents):
            workspace_dir = candidate / WORKSPACE_DIRNAME
            if workspace_dir.is_dir():
                return workspace_dir
        raise WorkspaceNotFoundError(
            f"no hephaes workspace found from {start_path}"
        )

    @staticmethod
    def _create_layout(paths: WorkspacePaths) -> None:
        paths.workspace_dir.mkdir(parents=True, exist_ok=True)
        paths.outputs_dir.mkdir(parents=True, exist_ok=True)
        paths.specs_dir.mkdir(parents=True, exist_ok=True)
        paths.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _initialize_database(self) -> None:
        with self._transaction() as connection:
            initialize_workspace_schema(connection)

    def _validate_database(self) -> None:
        if not self.workspace_dir.is_dir():
            raise WorkspaceNotFoundError(
                f"workspace directory does not exist: {self.workspace_dir}"
            )
        if not self.database_path.is_file():
            raise WorkspaceNotFoundError(
                f"workspace database does not exist: {self.database_path}"
            )

        with self._transaction() as connection:
            row = connection.execute(
                "SELECT value FROM workspace_meta WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                raise WorkspaceError(
                    f"workspace metadata is missing from {self.database_path}"
                )
            schema_version = int(row["value"])
            try:
                migrate_workspace_schema(connection, schema_version)
            except ValueError as exc:
                raise WorkspaceError(str(exc)) from exc

    def register_asset(
        self,
        asset_path: str | Path,
        *,
        on_duplicate: AssetRegistrationMode = "error",
    ) -> RegisteredAsset:
        normalized_path, file_type, file_size = _inspect_asset_path(asset_path)
        now = _utc_now()
        file_path = str(normalized_path)
        file_name = normalized_path.name

        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM assets WHERE file_path = ?",
                (file_path,),
            ).fetchone()

            if existing is not None:
                if on_duplicate == "skip":
                    return row_to_registered_asset(existing)
                if on_duplicate == "refresh":
                    connection.execute(
                        """
                        UPDATE assets
                        SET file_name = ?, file_type = ?, file_size = ?, updated_at = ?
                        WHERE file_path = ?
                        """,
                        (
                            file_name,
                            file_type,
                            file_size,
                            to_db_timestamp(now),
                            file_path,
                        ),
                    )
                    refreshed = connection.execute(
                        "SELECT * FROM assets WHERE file_path = ?",
                        (file_path,),
                    ).fetchone()
                    return row_to_registered_asset(refreshed)
                raise AssetAlreadyRegisteredError(
                    f"asset already registered: {file_path}"
                )

            asset_id = str(uuid4())
            timestamp = to_db_timestamp(now)
            connection.execute(
                """
                INSERT INTO assets(
                    id,
                    file_path,
                    file_name,
                    file_type,
                    file_size,
                    indexing_status,
                    registered_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    asset_id,
                    file_path,
                    file_name,
                    file_type,
                    file_size,
                    timestamp,
                    timestamp,
                ),
            )
            row = connection.execute(
                "SELECT * FROM assets WHERE id = ?",
                (asset_id,),
            ).fetchone()
            return row_to_registered_asset(row)

    def list_assets(self) -> list[RegisteredAsset]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM assets
                ORDER BY registered_at DESC, id DESC
                """
            ).fetchall()
        return [row_to_registered_asset(row) for row in rows]

    def get_asset(self, asset_id: str) -> RegisteredAsset | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM assets WHERE id = ?",
                (asset_id,),
            ).fetchone()
        if row is None:
            return None
        return row_to_registered_asset(row)

    def find_asset_by_path(self, asset_path: str | Path) -> RegisteredAsset | None:
        normalized_path = str(_normalize_asset_path(asset_path))
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM assets WHERE file_path = ?",
                (normalized_path,),
            ).fetchone()
        if row is None:
            return None
        return row_to_registered_asset(row)

    def resolve_asset(self, selector: str | Path) -> RegisteredAsset:
        asset = self.get_asset(str(selector))
        if asset is not None:
            return asset

        asset = self.find_asset_by_path(selector)
        if asset is not None:
            return asset

        raise AssetNotFoundError(f"asset not found: {selector}")

    def get_asset_or_raise(self, asset_id: str) -> RegisteredAsset:
        asset = self.get_asset(asset_id)
        if asset is None:
            raise AssetNotFoundError(f"asset not found: {asset_id}")
        return asset

    def get_asset_metadata(self, asset_id: str) -> IndexedAssetMetadata | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM asset_metadata WHERE asset_id = ?",
                (asset_id,),
            ).fetchone()
        if row is None:
            return None
        return row_to_indexed_asset_metadata(row)

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

        if isinstance(spec_document, ConversionSpec):
            document = build_conversion_spec_document(spec_document)
        else:
            document = load_conversion_spec_document(spec_document)

        config_id = str(uuid4())
        relative_document_path = f"{config_id}.json"
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
            row = connection.execute(
                "SELECT * FROM conversion_configs WHERE id = ?",
                (config_id,),
            ).fetchone()

        summary = row_to_saved_conversion_config_summary(
            row,
            document_path=str(document_path),
        )
        return build_saved_conversion_config(summary, document=document)

    def register_output_artifacts(
        self,
        *,
        output_root: str | Path,
        paths: list[str | Path] | None = None,
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
            candidate_paths = [
                path
                for path in sorted(root.rglob("*"))
                if path.is_file()
            ]
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
                    existing["created_at"]
                    if existing is not None
                    else to_db_timestamp(timestamp)
                )
                connection.execute(
                    """
                    INSERT INTO output_artifacts(
                        id,
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
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(output_path) DO UPDATE SET
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

        return [self.get_output_artifact_or_raise_by_path(path) for path in registered_paths]

    def run_conversion(
        self,
        source: str | Path,
        *,
        saved_config_selector: str | None = None,
        spec_document: ConversionSpecDocument | ConversionSpec | dict | str | Path | None = None,
        output_dir: str | Path | None = None,
        max_workers: int = 1,
    ) -> list[OutputArtifact]:
        if max_workers < 1:
            raise WorkspaceError("--max-workers must be >= 1")
        if (saved_config_selector is None) == (spec_document is None):
            raise WorkspaceError(
                "provide exactly one of saved_config_selector or spec_document"
            )

        registered_asset: RegisteredAsset | None = None
        try:
            registered_asset = self.resolve_asset(source)
            source_path = Path(registered_asset.file_path)
        except AssetNotFoundError:
            source_path, _file_type, _file_size = _inspect_asset_path(source)

        saved_config: SavedConversionConfig | None = None
        if saved_config_selector is not None:
            saved_config = self.resolve_saved_conversion_config(saved_config_selector)
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

        converter = Converter(
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

        return self.register_output_artifacts(
            output_root=resolved_output_dir,
            paths=[str(path) for path in artifact_paths],
            source_asset_id=registered_asset.id if registered_asset is not None else None,
            source_asset_path=str(source_path),
            saved_config_id=saved_config.id if saved_config is not None else None,
        )

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

    def index_asset(self, asset_id: str, *, max_workers: int = 1) -> RegisteredAsset:
        started_at = _utc_now()
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE assets
                SET indexing_status = 'indexing', updated_at = ?
                WHERE id = ?
                """,
                (to_db_timestamp(started_at), asset_id),
            )
            if connection.total_changes == 0:
                raise AssetNotFoundError(f"asset not found: {asset_id}")

        asset = self.get_asset_or_raise(asset_id)

        try:
            profile = profile_asset_file(asset.file_path, max_workers=max_workers)
            payload = build_index_metadata_payload(asset, profile)
        except Exception as exc:
            failed_at = _utc_now()
            with self._transaction() as connection:
                connection.execute(
                    """
                    UPDATE assets
                    SET indexing_status = 'failed', updated_at = ?
                    WHERE id = ?
                    """,
                    (to_db_timestamp(failed_at), asset_id),
                )
                upsert_asset_metadata(
                    connection,
                    asset_id=asset_id,
                    payload=None,
                    indexing_error=str(exc),
                    timestamp=failed_at,
                )
            raise

        finished_at = _utc_now()
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE assets
                SET indexing_status = 'indexed', last_indexed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    to_db_timestamp(finished_at),
                    to_db_timestamp(finished_at),
                    asset_id,
                ),
            )
            upsert_asset_metadata(
                connection,
                asset_id=asset_id,
                payload=payload,
                indexing_error=None,
                timestamp=finished_at,
            )

        return self.get_asset_or_raise(asset_id)

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
            _write_text_atomically(document_path, dump_conversion_spec_document(migrated_document, format="json"))
            self._update_saved_conversion_config_metadata(
                summary.id,
                spec_document_version=migrated_document.spec_version,
                invalid_reason=None,
                mark_opened=True,
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

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connect() as connection:
            try:
                yield connection
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()
