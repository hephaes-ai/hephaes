"""App-level registry for tracking backend workspaces."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from hephaes import Workspace, WorkspaceError
from hephaes.workspace.schema import WORKSPACE_DB_FILENAME, WORKSPACE_DIRNAME

WorkspaceRegistryStatus = str


class WorkspaceRegistryError(Exception):
    """Base exception for app-level workspace registry failures."""


class WorkspaceRegistryNotFoundError(WorkspaceRegistryError):
    """Raised when a requested workspace registry entry does not exist."""


@dataclass(frozen=True)
class RegisteredWorkspace:
    id: str
    name: str
    root_path: Path
    workspace_dir: Path
    database_path: Path
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime | None
    status: WorkspaceRegistryStatus
    status_reason: str | None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_db_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _from_db_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _normalize_root_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _default_workspace_name(root_path: Path) -> str:
    return root_path.name or str(root_path)


def _workspace_paths(root_path: Path) -> tuple[Path, Path]:
    workspace_dir = root_path / WORKSPACE_DIRNAME
    return workspace_dir, workspace_dir / WORKSPACE_DB_FILENAME


def _inspect_workspace_root(root_path: Path) -> tuple[WorkspaceRegistryStatus, str | None]:
    workspace_dir, database_path = _workspace_paths(root_path)
    if not workspace_dir.is_dir():
        return "missing", f"workspace directory does not exist: {workspace_dir}"
    if not database_path.is_file():
        return "missing", f"workspace database does not exist: {database_path}"

    try:
        Workspace.open(root_path)
    except WorkspaceError as exc:
        return "invalid", str(exc)

    return "ready", None


def _row_to_registered_workspace(row: sqlite3.Row) -> RegisteredWorkspace:
    return RegisteredWorkspace(
        id=row["id"],
        name=row["name"],
        root_path=Path(row["root_path"]),
        workspace_dir=Path(row["workspace_dir"]),
        database_path=Path(row["database_path"]),
        created_at=_from_db_timestamp(row["created_at"]) or _utc_now(),
        updated_at=_from_db_timestamp(row["updated_at"]) or _utc_now(),
        last_opened_at=_from_db_timestamp(row["last_opened_at"]),
        status=row["status"],
        status_reason=row["status_reason"],
    )


class WorkspaceRegistry:
    """Persist and reconcile the backend's known workspaces."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
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

    def initialize(self) -> None:
        with self._transaction() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    root_path TEXT NOT NULL UNIQUE,
                    workspace_dir TEXT NOT NULL,
                    database_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_opened_at TEXT NULL,
                    status TEXT NOT NULL,
                    status_reason TEXT NULL
                );

                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def list_workspaces(self, *, refresh_status: bool = True) -> list[RegisteredWorkspace]:
        rows = self._fetch_workspace_rows()
        if refresh_status:
            for row in rows:
                self.refresh_workspace_status(row["id"])
            rows = self._fetch_workspace_rows()
        return [_row_to_registered_workspace(row) for row in rows]

    def get_workspace(
        self,
        workspace_id: str,
        *,
        refresh_status: bool = False,
    ) -> RegisteredWorkspace:
        row = self._fetch_workspace_row(workspace_id)
        if row is None:
            raise WorkspaceRegistryNotFoundError(
                f"workspace registry entry not found: {workspace_id}"
            )
        if refresh_status:
            self.refresh_workspace_status(workspace_id)
            refreshed = self._fetch_workspace_row(workspace_id)
            if refreshed is None:
                raise WorkspaceRegistryNotFoundError(
                    f"workspace registry entry not found: {workspace_id}"
                )
            row = refreshed
        return _row_to_registered_workspace(row)

    def get_active_workspace_id(self) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM app_state WHERE key = 'active_workspace_id'"
            ).fetchone()
        if row is None:
            return None
        value = row["value"].strip()
        return value or None

    def set_active_workspace(
        self,
        workspace_id: str | None,
        *,
        update_last_opened: bool = True,
    ) -> RegisteredWorkspace | None:
        timestamp = _to_db_timestamp(_utc_now()) if update_last_opened else None
        with self._transaction() as connection:
            if workspace_id is None:
                connection.execute(
                    "DELETE FROM app_state WHERE key = 'active_workspace_id'"
                )
                return None

            row = connection.execute(
                "SELECT id FROM workspaces WHERE id = ?",
                (workspace_id,),
            ).fetchone()
            if row is None:
                raise WorkspaceRegistryNotFoundError(
                    f"workspace registry entry not found: {workspace_id}"
                )

            connection.execute(
                """
                INSERT INTO app_state(key, value)
                VALUES ('active_workspace_id', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (workspace_id,),
            )
            if timestamp is not None:
                connection.execute(
                    """
                    UPDATE workspaces
                    SET last_opened_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (timestamp, timestamp, workspace_id),
                )

        return self.get_workspace(workspace_id)

    def resolve_workspace_by_id(self, workspace_id: str) -> Workspace:
        registered_workspace = self.get_workspace(workspace_id, refresh_status=True)
        if registered_workspace.status != "ready":
            raise WorkspaceRegistryError(
                f"workspace is not ready: {workspace_id}"
            )
        try:
            return Workspace.open(registered_workspace.root_path)
        except WorkspaceError as exc:
            self._mark_workspace_invalid(workspace_id, str(exc))
            raise WorkspaceRegistryError(str(exc)) from exc

    def register_workspace(
        self,
        root_path: str | Path,
        *,
        name: str | None = None,
        activate: bool = False,
    ) -> RegisteredWorkspace:
        normalized_root = _normalize_root_path(root_path)
        workspace_dir, database_path = _workspace_paths(normalized_root)
        status, status_reason = _inspect_workspace_root(normalized_root)
        if activate and status != "ready":
            raise WorkspaceRegistryError(
                f"cannot activate a workspace with status '{status}'"
            )

        now = _to_db_timestamp(_utc_now())
        explicit_name = (name or "").strip() or None
        normalized_name = explicit_name or _default_workspace_name(normalized_root)

        with self._transaction() as connection:
            existing_row = connection.execute(
                "SELECT id, created_at, last_opened_at, name FROM workspaces WHERE root_path = ?",
                (str(normalized_root),),
            ).fetchone()
            if existing_row is None:
                workspace_id = f"ws_{uuid4().hex}"
                last_opened_at = now if activate else None
                connection.execute(
                    """
                    INSERT INTO workspaces(
                        id,
                        name,
                        root_path,
                        workspace_dir,
                        database_path,
                        created_at,
                        updated_at,
                        last_opened_at,
                        status,
                        status_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workspace_id,
                        normalized_name,
                        str(normalized_root),
                        str(workspace_dir),
                        str(database_path),
                        now,
                        now,
                        last_opened_at,
                        status,
                        status_reason,
                    ),
                )
            else:
                workspace_id = existing_row["id"]
                last_opened_at = now if activate else existing_row["last_opened_at"]
                next_name = explicit_name or existing_row["name"]
                connection.execute(
                    """
                    UPDATE workspaces
                    SET
                        name = ?,
                        workspace_dir = ?,
                        database_path = ?,
                        updated_at = ?,
                        last_opened_at = ?,
                        status = ?,
                        status_reason = ?
                    WHERE id = ?
                    """,
                    (
                        next_name,
                        str(workspace_dir),
                        str(database_path),
                        now,
                        last_opened_at,
                        status,
                        status_reason,
                        workspace_id,
                    ),
                )

        if activate:
            self.set_active_workspace(workspace_id, update_last_opened=False)

        return self.get_workspace(workspace_id)

    def remove_workspace(self, workspace_id: str) -> RegisteredWorkspace:
        workspace = self.get_workspace(workspace_id, refresh_status=False)
        with self._transaction() as connection:
            connection.execute(
                "DELETE FROM workspaces WHERE id = ?",
                (workspace_id,),
            )
            connection.execute(
                """
                DELETE FROM app_state
                WHERE key = 'active_workspace_id' AND value = ?
                """,
                (workspace_id,),
            )
        self.reconcile_active_workspace()
        return workspace

    def refresh_workspace_status(self, workspace_id: str) -> RegisteredWorkspace:
        workspace = self.get_workspace(workspace_id, refresh_status=False)
        status, status_reason = _inspect_workspace_root(workspace.root_path)
        now = _to_db_timestamp(_utc_now())
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE workspaces
                SET status = ?, status_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, status_reason, now, workspace_id),
            )
        return self.get_workspace(workspace_id, refresh_status=False)

    def reconcile_active_workspace(self) -> RegisteredWorkspace | None:
        workspaces = self.list_workspaces(refresh_status=True)
        ready_workspaces = [workspace for workspace in workspaces if workspace.status == "ready"]
        active_workspace_id = self.get_active_workspace_id()

        if active_workspace_id is not None:
            active_workspace = next(
                (workspace for workspace in ready_workspaces if workspace.id == active_workspace_id),
                None,
            )
            if active_workspace is not None:
                return active_workspace

        if not ready_workspaces:
            self.set_active_workspace(None, update_last_opened=False)
            return None

        selected_workspace = sorted(
            ready_workspaces,
            key=lambda workspace: (
                workspace.last_opened_at is None,
                -(workspace.last_opened_at.timestamp()) if workspace.last_opened_at is not None else 0.0,
                workspace.created_at.timestamp(),
                workspace.id,
            ),
        )[0]
        self.set_active_workspace(selected_workspace.id, update_last_opened=False)
        return self.get_workspace(selected_workspace.id)

    def resolve_active_workspace(self) -> Workspace | None:
        attempted_ids: set[str] = set()
        while True:
            active_workspace = self.reconcile_active_workspace()
            if active_workspace is None:
                return None
            if active_workspace.id in attempted_ids:
                return None
            attempted_ids.add(active_workspace.id)
            try:
                return Workspace.open(active_workspace.root_path)
            except WorkspaceError as exc:
                self._mark_workspace_invalid(active_workspace.id, str(exc))
                continue

    def _fetch_workspace_rows(self) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT
                        id,
                        name,
                        root_path,
                        workspace_dir,
                        database_path,
                        created_at,
                        updated_at,
                        last_opened_at,
                        status,
                        status_reason
                    FROM workspaces
                    ORDER BY
                        last_opened_at IS NULL,
                        last_opened_at DESC,
                        created_at ASC,
                        id ASC
                    """
                ).fetchall()
            )

    def _fetch_workspace_row(self, workspace_id: str) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT
                    id,
                    name,
                    root_path,
                    workspace_dir,
                    database_path,
                    created_at,
                    updated_at,
                    last_opened_at,
                    status,
                    status_reason
                FROM workspaces
                WHERE id = ?
                """,
                (workspace_id,),
            ).fetchone()

    def _mark_workspace_invalid(self, workspace_id: str, reason: str) -> None:
        now = _to_db_timestamp(_utc_now())
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE workspaces
                SET status = 'invalid', status_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (reason, now, workspace_id),
            )
