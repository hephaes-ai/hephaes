from __future__ import annotations

from ..errors import ConversionConfigNotFoundError
from ..models import (
    SavedConversionConfig,
    SavedConversionConfigRevision,
    SavedConversionConfigRevisionSummary,
    SavedConversionConfigSummary,
)
from ..serialization import (
    row_to_saved_conversion_config_revision_summary,
    row_to_saved_conversion_config_summary,
)
from ..utils import _normalize_name


class WorkspaceConfigQueryMixin:
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
