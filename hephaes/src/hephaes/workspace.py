from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator, Literal
from uuid import uuid4

from .metrics import infer_topic_modality, summarize_bag_topics
from .models import BagMetadata
from .profiler import Profiler

SUPPORTED_ASSET_FILE_TYPES = frozenset({"bag", "mcap"})
WORKSPACE_DIRNAME = ".hephaes"
WORKSPACE_DB_FILENAME = "workspace.sqlite3"
WORKSPACE_SCHEMA_VERSION = 2

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


class AssetNotFoundError(WorkspaceError):
    """Raised when a requested asset cannot be found in the workspace."""


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
    last_indexed_at: datetime | None


@dataclass(frozen=True)
class IndexedAssetMetadata:
    asset_id: str
    duration: float | None
    start_time: datetime | None
    end_time: datetime | None
    topic_count: int
    message_count: int
    sensor_types: list[str]
    topics: list[dict[str, object]]
    default_episode: dict[str, object] | None
    visualization_summary: dict[str, object] | None
    raw_metadata: dict[str, object]
    indexing_error: str | None
    created_at: datetime
    updated_at: datetime


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


def _timestamp_ns_to_datetime(timestamp_ns: int | None) -> datetime | None:
    if timestamp_ns is None:
        return None
    return datetime.fromtimestamp(timestamp_ns / 1e9, tz=UTC)


def profile_asset_file(file_path: str, *, max_workers: int = 1) -> BagMetadata:
    return Profiler([file_path], max_workers=max_workers).profile()[0]


def _build_index_metadata_payload(asset: RegisteredAsset, profile: BagMetadata) -> dict[str, object]:
    topic_summary = summarize_bag_topics(profile)
    topics_payload: list[dict[str, object]] = []
    sensor_types = [
        sensor_family
        for sensor_family in topic_summary.sensor_family_counts
        if sensor_family != "other"
    ]

    for topic in profile.topics:
        topics_payload.append(
            {
                "name": topic.name,
                "message_type": topic.message_type,
                "message_count": topic.message_count,
                "rate_hz": topic.rate_hz,
                "modality": infer_topic_modality(topic.message_type),
            }
        )

    if not sensor_types and topics_payload:
        sensor_types = ["other"]

    return {
        "duration": profile.duration_seconds,
        "start_time": _timestamp_ns_to_datetime(profile.start_timestamp),
        "end_time": _timestamp_ns_to_datetime(profile.end_timestamp),
        "topic_count": len(topics_payload),
        "message_count": profile.message_count,
        "sensor_types": sensor_types,
        "topics": topics_payload,
        "default_episode": {
            "episode_id": f"{asset.id}:default",
            "label": "Episode 1",
            "duration": profile.duration_seconds,
        },
        "visualization_summary": {
            "has_visualizable_streams": topic_summary.visualization.has_visualizable_streams,
            "default_lane_count": topic_summary.visualization.visualizable_stream_count,
        },
        "raw_metadata": {
            "compression_format": profile.compression_format,
            "file_path": profile.file_path,
            "file_size_bytes": profile.file_size_bytes,
            "path": profile.path,
            "ros_version": profile.ros_version,
            "storage_format": profile.storage_format,
        },
    }


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
                    last_indexed_at TEXT NULL,
                    registered_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS asset_metadata (
                    asset_id TEXT PRIMARY KEY,
                    duration REAL NULL,
                    start_time TEXT NULL,
                    end_time TEXT NULL,
                    topic_count INTEGER NOT NULL DEFAULT 0,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    sensor_types_json TEXT NOT NULL DEFAULT '[]',
                    topics_json TEXT NOT NULL DEFAULT '[]',
                    default_episode_json TEXT NULL,
                    visualization_summary_json TEXT NULL,
                    raw_metadata_json TEXT NOT NULL DEFAULT '{}',
                    indexing_error TEXT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
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

        with self._transaction() as connection:
            row = connection.execute(
                "SELECT value FROM workspace_meta WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                raise WorkspaceError(
                    f"workspace metadata is missing from {self.database_path}"
                )
            schema_version = int(row["value"])
            self._migrate_database(connection, schema_version)

    def _migrate_database(self, connection: sqlite3.Connection, schema_version: int) -> None:
        if schema_version == WORKSPACE_SCHEMA_VERSION:
            return

        if schema_version == 1:
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(assets)").fetchall()
            }
            if "last_indexed_at" not in columns:
                connection.execute("ALTER TABLE assets ADD COLUMN last_indexed_at TEXT NULL")

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS asset_metadata (
                    asset_id TEXT PRIMARY KEY,
                    duration REAL NULL,
                    start_time TEXT NULL,
                    end_time TEXT NULL,
                    topic_count INTEGER NOT NULL DEFAULT 0,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    sensor_types_json TEXT NOT NULL DEFAULT '[]',
                    topics_json TEXT NOT NULL DEFAULT '[]',
                    default_episode_json TEXT NULL,
                    visualization_summary_json TEXT NULL,
                    raw_metadata_json TEXT NOT NULL DEFAULT '{}',
                    indexing_error TEXT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                "UPDATE workspace_meta SET value = ? WHERE key = 'schema_version'",
                (str(WORKSPACE_SCHEMA_VERSION),),
            )
            return

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
        return self._row_to_indexed_asset_metadata(row)

    def index_asset(self, asset_id: str, *, max_workers: int = 1) -> RegisteredAsset:
        started_at = _utc_now()
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE assets
                SET indexing_status = 'indexing', updated_at = ?
                WHERE id = ?
                """,
                (_to_db_timestamp(started_at), asset_id),
            )
            if connection.total_changes == 0:
                raise AssetNotFoundError(f"asset not found: {asset_id}")

        asset = self.get_asset_or_raise(asset_id)

        try:
            profile = profile_asset_file(asset.file_path, max_workers=max_workers)
            payload = _build_index_metadata_payload(asset, profile)
        except Exception as exc:
            failed_at = _utc_now()
            with self._transaction() as connection:
                connection.execute(
                    """
                    UPDATE assets
                    SET indexing_status = 'failed', updated_at = ?
                    WHERE id = ?
                    """,
                    (_to_db_timestamp(failed_at), asset_id),
                )
                self._upsert_asset_metadata(
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
                    _to_db_timestamp(finished_at),
                    _to_db_timestamp(finished_at),
                    asset_id,
                ),
            )
            self._upsert_asset_metadata(
                connection,
                asset_id=asset_id,
                payload=payload,
                indexing_error=None,
                timestamp=finished_at,
            )

        return self.get_asset_or_raise(asset_id)

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
            last_indexed_at=(
                _from_db_timestamp(row["last_indexed_at"])
                if row["last_indexed_at"] is not None
                else None
            ),
        )

    @staticmethod
    def _row_to_indexed_asset_metadata(row: sqlite3.Row) -> IndexedAssetMetadata:
        return IndexedAssetMetadata(
            asset_id=row["asset_id"],
            duration=row["duration"],
            start_time=(
                _from_db_timestamp(row["start_time"])
                if row["start_time"] is not None
                else None
            ),
            end_time=(
                _from_db_timestamp(row["end_time"])
                if row["end_time"] is not None
                else None
            ),
            topic_count=int(row["topic_count"]),
            message_count=int(row["message_count"]),
            sensor_types=list(json.loads(row["sensor_types_json"])),
            topics=list(json.loads(row["topics_json"])),
            default_episode=(
                dict(json.loads(row["default_episode_json"]))
                if row["default_episode_json"] is not None
                else None
            ),
            visualization_summary=(
                dict(json.loads(row["visualization_summary_json"]))
                if row["visualization_summary_json"] is not None
                else None
            ),
            raw_metadata=dict(json.loads(row["raw_metadata_json"])),
            indexing_error=row["indexing_error"],
            created_at=_from_db_timestamp(row["created_at"]),
            updated_at=_from_db_timestamp(row["updated_at"]),
        )

    @staticmethod
    def _upsert_asset_metadata(
        connection: sqlite3.Connection,
        *,
        asset_id: str,
        payload: dict[str, object] | None,
        indexing_error: str | None,
        timestamp: datetime,
    ) -> None:
        existing = connection.execute(
            "SELECT created_at FROM asset_metadata WHERE asset_id = ?",
            (asset_id,),
        ).fetchone()
        created_at = (
            existing["created_at"] if existing is not None else _to_db_timestamp(timestamp)
        )
        payload = payload or {}
        connection.execute(
            """
            INSERT INTO asset_metadata(
                asset_id,
                duration,
                start_time,
                end_time,
                topic_count,
                message_count,
                sensor_types_json,
                topics_json,
                default_episode_json,
                visualization_summary_json,
                raw_metadata_json,
                indexing_error,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(asset_id) DO UPDATE SET
                duration = excluded.duration,
                start_time = excluded.start_time,
                end_time = excluded.end_time,
                topic_count = excluded.topic_count,
                message_count = excluded.message_count,
                sensor_types_json = excluded.sensor_types_json,
                topics_json = excluded.topics_json,
                default_episode_json = excluded.default_episode_json,
                visualization_summary_json = excluded.visualization_summary_json,
                raw_metadata_json = excluded.raw_metadata_json,
                indexing_error = excluded.indexing_error,
                updated_at = excluded.updated_at
            """,
            (
                asset_id,
                payload.get("duration"),
                _to_db_timestamp(payload["start_time"]) if payload.get("start_time") is not None else None,
                _to_db_timestamp(payload["end_time"]) if payload.get("end_time") is not None else None,
                int(payload.get("topic_count", 0)),
                int(payload.get("message_count", 0)),
                json.dumps(payload.get("sensor_types", [])),
                json.dumps(payload.get("topics", [])),
                json.dumps(payload["default_episode"]) if payload.get("default_episode") is not None else None,
                json.dumps(payload["visualization_summary"]) if payload.get("visualization_summary") is not None else None,
                json.dumps(payload.get("raw_metadata", {})),
                indexing_error,
                created_at,
                _to_db_timestamp(timestamp),
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
