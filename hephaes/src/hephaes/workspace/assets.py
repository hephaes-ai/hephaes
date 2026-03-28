from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from .errors import AssetAlreadyRegisteredError, AssetNotFoundError
from .indexing import build_index_metadata_payload
from .models import AssetRegistrationMode, IndexedAssetMetadata, RegisteredAsset
from .serialization import (
    row_to_indexed_asset_metadata,
    row_to_registered_asset,
    to_db_timestamp,
    upsert_asset_metadata,
)
from .utils import _inspect_asset_path, _normalize_asset_path, _utc_now


class WorkspaceAssetMixin:
    def register_asset(
        self,
        asset_path: str | Path,
        *,
        on_duplicate: AssetRegistrationMode = "error",
    ) -> RegisteredAsset:
        normalized_file_path, file_type, file_size = _inspect_asset_path(asset_path)
        now = _utc_now()
        file_path = str(normalized_file_path)
        file_name = normalized_file_path.name

        with self._transaction() as connection:
            existing = connection.execute(
                """
                SELECT *
                FROM assets
                WHERE file_path = ?
                """,
                (file_path,),
            ).fetchone()

            if existing is not None:
                existing_asset = row_to_registered_asset(existing)
                if on_duplicate == "skip":
                    return existing_asset
                if on_duplicate == "refresh":
                    connection.execute(
                        """
                        UPDATE assets
                        SET file_name = ?, file_type = ?, file_size = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            file_name,
                            file_type,
                            file_size,
                            to_db_timestamp(now),
                            existing_asset.id,
                        ),
                    )
                    refreshed = connection.execute(
                        "SELECT * FROM assets WHERE id = ?",
                        (existing_asset.id,),
                    ).fetchone()
                    return row_to_registered_asset(refreshed)
                raise AssetAlreadyRegisteredError(f"asset already registered: {file_path}")

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
                    last_indexed_at,
                    registered_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', NULL, ?, ?)
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
                """,
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

    def index_asset(
        self,
        asset_id: str,
        *,
        max_workers: int = 1,
        job_config: dict | None = None,
        profile_path: str | Path | None = None,
        profile_fn: Any | None = None,
    ) -> RegisteredAsset:
        from . import profile_asset_file as profile_asset_file_impl

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
            resolved_profile_path = (
                str(Path(profile_path).expanduser())
                if profile_path is not None
                else asset.file_path
            )
            if profile_fn is None:
                profile = profile_asset_file_impl(
                    resolved_profile_path,
                    max_workers=max_workers,
                )
            else:
                profile = profile_fn(resolved_profile_path)
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
