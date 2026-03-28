from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .errors import TagAlreadyExistsError, TagNotFoundError, WorkspaceError
from .models import WorkspaceTag
from .serialization import row_to_workspace_tag, to_db_timestamp
from .utils import _normalize_name, _utc_now


class WorkspaceTagMixin:
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
