from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator, Literal
from uuid import uuid4

SUPPORTED_ASSET_FILE_TYPES = frozenset({"bag", "mcap"})
WORKSPACE_DIRNAME = ".hephaes"
WORKSPACE_DB_FILENAME = "workspace.sqlite3"
WORKSPACE_SCHEMA_VERSION = 1

AssetRegistrationMode = Literal["error", "skip", "refresh"]


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


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path
    workspace_dir: Path
    database_path: Path
    outputs_dir: Path
    specs_dir: Path
    jobs_dir: Path


@dataclass(frozen=True)
class RegisteredAsset:
    id: str
    file_path: str
    file_name: str
    file_type: str
    file_size: int
    registered_at: datetime
    updated_at: datetime
    indexing_status: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_db_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _from_db_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


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
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;

                CREATE TABLE IF NOT EXISTS workspace_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    indexing_status TEXT NOT NULL DEFAULT 'pending',
                    registered_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_assets_registered_at
                ON assets(registered_at DESC, id DESC);
                """
            )
            connection.execute(
                """
                INSERT INTO workspace_meta(key, value)
                VALUES ('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(WORKSPACE_SCHEMA_VERSION),),
            )

    def _validate_database(self) -> None:
        if not self.workspace_dir.is_dir():
            raise WorkspaceNotFoundError(
                f"workspace directory does not exist: {self.workspace_dir}"
            )
        if not self.database_path.is_file():
            raise WorkspaceNotFoundError(
                f"workspace database does not exist: {self.database_path}"
            )

        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM workspace_meta WHERE key = 'schema_version'"
            ).fetchone()
        if row is None:
            raise WorkspaceError(
                f"workspace metadata is missing from {self.database_path}"
            )
        schema_version = int(row["value"])
        if schema_version != WORKSPACE_SCHEMA_VERSION:
            raise WorkspaceError(
                "workspace schema version mismatch: "
                f"expected {WORKSPACE_SCHEMA_VERSION}, got {schema_version}"
            )

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
                    return self._row_to_registered_asset(existing)
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
                            _to_db_timestamp(now),
                            file_path,
                        ),
                    )
                    refreshed = connection.execute(
                        "SELECT * FROM assets WHERE file_path = ?",
                        (file_path,),
                    ).fetchone()
                    return self._row_to_registered_asset(refreshed)
                raise AssetAlreadyRegisteredError(
                    f"asset already registered: {file_path}"
                )

            asset_id = str(uuid4())
            timestamp = _to_db_timestamp(now)
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
            return self._row_to_registered_asset(row)

    def list_assets(self) -> list[RegisteredAsset]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM assets
                ORDER BY registered_at DESC, id DESC
                """
            ).fetchall()
        return [self._row_to_registered_asset(row) for row in rows]

    def get_asset(self, asset_id: str) -> RegisteredAsset | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM assets WHERE id = ?",
                (asset_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_registered_asset(row)

    @staticmethod
    def _row_to_registered_asset(row: sqlite3.Row) -> RegisteredAsset:
        return RegisteredAsset(
            id=row["id"],
            file_path=row["file_path"],
            file_name=row["file_name"],
            file_type=row["file_type"],
            file_size=int(row["file_size"]),
            registered_at=_from_db_timestamp(row["registered_at"]),
            updated_at=_from_db_timestamp(row["updated_at"]),
            indexing_status=row["indexing_status"],
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
