from __future__ import annotations

import json
import mimetypes
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from ._workspace_indexing import build_index_metadata_payload, profile_asset_file
from ._workspace_models import (
    AssetRegistrationMode,
    ConversionRun,
    ConversionDraftRevision,
    ConversionDraftRevisionSummary,
    DefaultEpisodeSummary,
    IndexedAssetMetadata,
    IndexedTopicSummary,
    OutputArtifact,
    OutputArtifactSummary,
    RegisteredAsset,
    SavedConversionConfig,
    SavedConversionConfigRevision,
    SavedConversionConfigRevisionSummary,
    SavedConversionConfigSummary,
    SourceAssetMetadata,
    VisualizationSummary,
    WorkspaceJob,
    WorkspaceTag,
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
    build_conversion_draft_revision,
    build_saved_conversion_config,
    build_saved_conversion_config_revision,
    from_db_timestamp,
    row_to_conversion_run,
    row_to_conversion_draft_revision_summary,
    row_to_indexed_asset_metadata,
    row_to_output_artifact,
    row_to_output_artifact_summary,
    row_to_registered_asset,
    row_to_saved_conversion_config_revision_summary,
    row_to_saved_conversion_config_summary,
    row_to_workspace_job,
    row_to_workspace_tag,
    to_db_timestamp,
    upsert_asset_metadata,
)
from ._converter_helpers import _normalize_payload
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


class TagAlreadyExistsError(WorkspaceError):
    """Raised when a tag with the requested name already exists."""


class TagNotFoundError(WorkspaceError):
    """Raised when a requested tag cannot be found in the workspace."""


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


def _copy_file_atomically(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination_path.with_name(f".{destination_path.name}.tmp")
    shutil.copy2(source_path, temporary_path)
    temporary_path.replace(destination_path)


def _load_conversion_document_input(
    spec_document: ConversionSpecDocument | ConversionSpec | dict | str | Path,
) -> ConversionSpecDocument:
    if isinstance(spec_document, ConversionSpec):
        return build_conversion_spec_document(spec_document)
    return load_conversion_spec_document(spec_document)


def _build_config_document_relative_path(config_id: str) -> str:
    return f"{config_id}.json"


def _build_config_revision_relative_path(revision_id: str) -> str:
    return f"revisions/{revision_id}.json"


def _build_draft_revision_relative_path(draft_id: str) -> str:
    return f"drafts/{draft_id}.json"


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
            imports_dir=workspace_dir / "imports",
            outputs_dir=workspace_dir / "outputs",
            specs_dir=workspace_dir / "specs",
            spec_revisions_dir=workspace_dir / "specs" / "revisions",
            draft_revisions_dir=workspace_dir / "specs" / "drafts",
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
            imports_dir=workspace_dir / "imports",
            outputs_dir=workspace_dir / "outputs",
            specs_dir=workspace_dir / "specs",
            spec_revisions_dir=workspace_dir / "specs" / "revisions",
            draft_revisions_dir=workspace_dir / "specs" / "drafts",
            jobs_dir=workspace_dir / "jobs",
        )
        cls._create_layout(paths)
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
        paths.imports_dir.mkdir(parents=True, exist_ok=True)
        paths.outputs_dir.mkdir(parents=True, exist_ok=True)
        paths.specs_dir.mkdir(parents=True, exist_ok=True)
        paths.spec_revisions_dir.mkdir(parents=True, exist_ok=True)
        paths.draft_revisions_dir.mkdir(parents=True, exist_ok=True)
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

    def _build_import_destination(self, *, asset_id: str, source_path: Path) -> Path:
        return self.paths.imports_dir / asset_id / source_path.name

    def import_asset(
        self,
        asset_path: str | Path,
        *,
        on_duplicate: AssetRegistrationMode = "error",
    ) -> RegisteredAsset:
        normalized_source_path, file_type, _file_size = _inspect_asset_path(asset_path)
        now = _utc_now()
        source_path = str(normalized_source_path)
        file_name = normalized_source_path.name

        with self._transaction() as connection:
            existing = connection.execute(
                """
                SELECT *
                FROM assets
                WHERE source_path = ?
                   OR file_path = ?
                """,
                (source_path, source_path),
            ).fetchone()

            if existing is not None:
                existing_asset = row_to_registered_asset(existing)
                if on_duplicate == "skip":
                    return existing_asset
                if on_duplicate == "refresh":
                    imported_path = Path(existing_asset.file_path)
                    _copy_file_atomically(normalized_source_path, imported_path)
                    connection.execute(
                        """
                        UPDATE assets
                        SET source_path = ?, file_name = ?, file_type = ?, file_size = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            source_path,
                            file_name,
                            file_type,
                            imported_path.stat().st_size,
                            to_db_timestamp(now),
                            existing_asset.id,
                        ),
                    )
                    refreshed = connection.execute(
                        "SELECT * FROM assets WHERE id = ?",
                        (existing_asset.id,),
                    ).fetchone()
                    return row_to_registered_asset(refreshed)
                raise AssetAlreadyRegisteredError(
                    f"asset already registered: {source_path}"
                )

            asset_id = str(uuid4())
            imported_path = self._build_import_destination(
                asset_id=asset_id,
                source_path=normalized_source_path,
            )
            _copy_file_atomically(normalized_source_path, imported_path)
            imported_size = imported_path.stat().st_size
            timestamp = to_db_timestamp(now)
            connection.execute(
                """
                INSERT INTO assets(
                    id,
                    file_path,
                    source_path,
                    file_name,
                    file_type,
                    file_size,
                    indexing_status,
                    last_indexed_at,
                    imported_at,
                    registered_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL, ?, ?, ?)
                """,
                (
                    asset_id,
                    str(imported_path),
                    source_path,
                    file_name,
                    file_type,
                    imported_size,
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
            row = connection.execute(
                "SELECT * FROM assets WHERE id = ?",
                (asset_id,),
            ).fetchone()
            return row_to_registered_asset(row)

    def register_asset(
        self,
        asset_path: str | Path,
        *,
        on_duplicate: AssetRegistrationMode = "error",
    ) -> RegisteredAsset:
        return self.import_asset(asset_path, on_duplicate=on_duplicate)

    def list_assets(self, *, tags: list[str] | None = None) -> list[RegisteredAsset]:
        with self._connect() as connection:
            if tags:
                resolved_tags = [self.resolve_tag(tag) for tag in tags]
                placeholders = ", ".join("?" for _ in resolved_tags)
                rows = connection.execute(
                    f"""
                    SELECT assets.*
                    FROM assets
                    JOIN asset_tags ON asset_tags.asset_id = assets.id
                    WHERE asset_tags.tag_id IN ({placeholders})
                    GROUP BY assets.id
                    HAVING COUNT(DISTINCT asset_tags.tag_id) = ?
                    ORDER BY assets.registered_at DESC, assets.id DESC
                    """,
                    (*[tag.id for tag in resolved_tags], len(resolved_tags)),
                ).fetchall()
            else:
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
                """
                SELECT *
                FROM assets
                WHERE file_path = ?
                   OR source_path = ?
                """,
                (normalized_path, normalized_path),
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

    def list_tags(self) -> list[WorkspaceTag]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM tags
                ORDER BY name ASC, id ASC
                """
            ).fetchall()
        return [row_to_workspace_tag(row) for row in rows]

    def create_tag(self, name: str) -> WorkspaceTag:
        normalized_name = _normalize_name(name)
        if not normalized_name:
            raise WorkspaceError("tag name must be non-empty")

        now = _utc_now()
        tag_id = str(uuid4())
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM tags WHERE normalized_name = ?",
                (normalized_name,),
            ).fetchone()
            if existing is not None:
                raise TagAlreadyExistsError(f"tag already exists: {name}")
            connection.execute(
                """
                INSERT INTO tags(id, name, normalized_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    tag_id,
                    name.strip(),
                    normalized_name,
                    to_db_timestamp(now),
                    to_db_timestamp(now),
                ),
            )
            row = connection.execute(
                "SELECT * FROM tags WHERE id = ?",
                (tag_id,),
            ).fetchone()
        return row_to_workspace_tag(row)

    def delete_tag(self, tag_selector: str) -> WorkspaceTag:
        tag = self.resolve_tag(tag_selector)
        with self._transaction() as connection:
            connection.execute("DELETE FROM asset_tags WHERE tag_id = ?", (tag.id,))
            connection.execute("DELETE FROM tags WHERE id = ?", (tag.id,))
        return tag

    def get_tag(self, tag_id: str) -> WorkspaceTag | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM tags WHERE id = ?",
                (tag_id,),
            ).fetchone()
        if row is None:
            return None
        return row_to_workspace_tag(row)

    def find_tag_by_name(self, name: str) -> WorkspaceTag | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM tags WHERE normalized_name = ?",
                (_normalize_name(name),),
            ).fetchone()
        if row is None:
            return None
        return row_to_workspace_tag(row)

    def resolve_tag(self, selector: str) -> WorkspaceTag:
        tag = self.get_tag(selector)
        if tag is not None:
            return tag
        tag = self.find_tag_by_name(selector)
        if tag is not None:
            return tag
        raise TagNotFoundError(f"tag not found: {selector}")

    def get_asset_tags(self, asset_id: str) -> list[WorkspaceTag]:
        self.get_asset_or_raise(asset_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT tags.*
                FROM tags
                JOIN asset_tags ON asset_tags.tag_id = tags.id
                WHERE asset_tags.asset_id = ?
                ORDER BY tags.name ASC, tags.id ASC
                """,
                (asset_id,),
            ).fetchall()
        return [row_to_workspace_tag(row) for row in rows]

    def attach_tag_to_asset(self, asset_selector: str | Path, tag_selector: str) -> WorkspaceTag:
        asset = self.resolve_asset(asset_selector)
        tag = self.resolve_tag(tag_selector)
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO asset_tags(asset_id, tag_id, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(asset_id, tag_id) DO NOTHING
                """,
                (
                    asset.id,
                    tag.id,
                    to_db_timestamp(_utc_now()),
                ),
            )
        return tag

    def remove_tag_from_asset(self, asset_selector: str | Path, tag_selector: str) -> WorkspaceTag:
        asset = self.resolve_asset(asset_selector)
        tag = self.resolve_tag(tag_selector)
        with self._transaction() as connection:
            connection.execute(
                "DELETE FROM asset_tags WHERE asset_id = ? AND tag_id = ?",
                (asset.id, tag.id),
            )
        return tag

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

        def _json_safe_optional_payload(value: dict[str, Any] | Any | None) -> dict[str, Any] | None:
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
        draft_id = str(uuid4())
        relative_document_path = _build_draft_revision_relative_path(draft_id)
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
                INSERT INTO conversion_draft_revisions(
                    id,
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
                    preview_json,
                    spec_document_path,
                    spec_document_version,
                    invalid_reason,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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
                (draft_id,),
            ).fetchone()

        summary = row_to_conversion_draft_revision_summary(
            row,
            document_path=str(document_path),
        )
        return build_conversion_draft_revision(summary, document=document)

    def create_job(
        self,
        *,
        kind: str,
        target_asset_ids: list[str] | None = None,
        config: dict | None = None,
        job_id: str | None = None,
    ) -> WorkspaceJob:
        timestamp = _utc_now()
        job_id = job_id or str(uuid4())
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO jobs(
                    id,
                    kind,
                    status,
                    target_asset_ids_json,
                    config_json,
                    conversion_run_id,
                    error_message,
                    created_at,
                    updated_at,
                    started_at,
                    completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    kind,
                    "pending",
                    json.dumps(target_asset_ids or []),
                    json.dumps(config or {}),
                    None,
                    None,
                    to_db_timestamp(timestamp),
                    to_db_timestamp(timestamp),
                    None,
                    None,
                ),
            )
        return self.get_job_or_raise(job_id)

    def list_jobs(self) -> list[WorkspaceJob]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM jobs
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        return [row_to_workspace_job(row) for row in rows]

    def get_job(self, job_id: str) -> WorkspaceJob | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return row_to_workspace_job(row)

    def get_job_or_raise(self, job_id: str) -> WorkspaceJob:
        job = self.get_job(job_id)
        if job is None:
            raise WorkspaceError(f"job not found: {job_id}")
        return job

    def mark_job_running(self, job_id: str) -> WorkspaceJob:
        timestamp = _utc_now()
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'running', updated_at = ?, started_at = COALESCE(started_at, ?)
                WHERE id = ?
                """,
                (
                    to_db_timestamp(timestamp),
                    to_db_timestamp(timestamp),
                    job_id,
                ),
            )
        return self.get_job_or_raise(job_id)

    def mark_job_succeeded(
        self,
        job_id: str,
        *,
        conversion_run_id: str | None = None,
    ) -> WorkspaceJob:
        timestamp = _utc_now()
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'succeeded', conversion_run_id = COALESCE(?, conversion_run_id),
                    error_message = NULL, updated_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    conversion_run_id,
                    to_db_timestamp(timestamp),
                    to_db_timestamp(timestamp),
                    job_id,
                ),
            )
        return self.get_job_or_raise(job_id)

    def mark_job_failed(self, job_id: str, *, error_message: str) -> WorkspaceJob:
        timestamp = _utc_now()
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'failed', error_message = ?, updated_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    error_message,
                    to_db_timestamp(timestamp),
                    to_db_timestamp(timestamp),
                    job_id,
                ),
            )
        return self.get_job_or_raise(job_id)

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
            registered_asset.source_path if registered_asset is not None and registered_asset.source_path is not None else str(source_path)
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

            outputs = self.register_output_artifacts(
                output_root=resolved_output_dir,
                paths=[str(path) for path in artifact_paths],
                conversion_run_id=run.id,
                source_asset_id=registered_asset.id if registered_asset is not None else None,
                source_asset_path=(
                    registered_asset.source_path
                    if registered_asset is not None
                    else str(source_path)
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

    def index_asset(
        self,
        asset_id: str,
        *,
        max_workers: int = 1,
        job_config: dict | None = None,
    ) -> RegisteredAsset:
        self.get_asset_or_raise(asset_id)
        job = self.create_job(
            kind="index_asset",
            target_asset_ids=[asset_id],
            config={"max_workers": max_workers, **(job_config or {})},
        )
        self.mark_job_running(job.id)
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
            self.mark_job_failed(job.id, error_message=str(exc))
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
        self.mark_job_succeeded(job.id)

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
                    revision_number=self._next_conversion_config_revision_number(connection, summary.id),
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
