from __future__ import annotations

import sqlite3

WORKSPACE_DIRNAME = ".hephaes"
WORKSPACE_DB_FILENAME = "workspace.sqlite3"
WORKSPACE_SCHEMA_VERSION = 11


def initialize_workspace_schema(connection: sqlite3.Connection) -> None:
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

        CREATE TABLE IF NOT EXISTS tags (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS asset_tags (
            asset_id TEXT NOT NULL,
            tag_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY(asset_id, tag_id),
            FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE,
            FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS conversion_configs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL UNIQUE,
            description TEXT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            spec_document_path TEXT NOT NULL,
            spec_document_version INTEGER NOT NULL,
            invalid_reason TEXT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_opened_at TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS conversion_config_revisions (
            id TEXT PRIMARY KEY,
            config_id TEXT NOT NULL,
            revision_number INTEGER NOT NULL,
            description TEXT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            spec_document_path TEXT NOT NULL,
            spec_document_version INTEGER NOT NULL,
            invalid_reason TEXT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(config_id) REFERENCES conversion_configs(id) ON DELETE CASCADE
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_conversion_config_revisions_config_revision
        ON conversion_config_revisions(config_id, revision_number);

        CREATE TABLE IF NOT EXISTS conversion_drafts (
            id TEXT PRIMARY KEY,
            source_asset_id TEXT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            current_revision_id TEXT NULL,
            confirmed_revision_id TEXT NULL,
            saved_config_id TEXT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            discarded_at TEXT NULL,
            FOREIGN KEY(source_asset_id) REFERENCES assets(id) ON DELETE SET NULL,
            FOREIGN KEY(saved_config_id) REFERENCES conversion_configs(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_conversion_drafts_source_asset_id
        ON conversion_drafts(source_asset_id);

        CREATE INDEX IF NOT EXISTS idx_conversion_drafts_saved_config_id
        ON conversion_drafts(saved_config_id);

        CREATE TABLE IF NOT EXISTS conversion_draft_revisions (
            id TEXT PRIMARY KEY,
            draft_id TEXT NULL,
            revision_number INTEGER NOT NULL DEFAULT 1,
            label TEXT NULL,
            saved_config_id TEXT NULL,
            source_asset_id TEXT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            inspection_request_json TEXT NOT NULL DEFAULT '{}',
            inspection_json TEXT NOT NULL DEFAULT '{}',
            draft_request_json TEXT NOT NULL DEFAULT '{}',
            draft_result_json TEXT NOT NULL DEFAULT '{}',
            preview_request_json TEXT NOT NULL DEFAULT '{}',
            preview_json TEXT NULL,
            spec_document_path TEXT NOT NULL,
            spec_document_version INTEGER NOT NULL,
            invalid_reason TEXT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(draft_id) REFERENCES conversion_drafts(id) ON DELETE CASCADE,
            FOREIGN KEY(saved_config_id) REFERENCES conversion_configs(id) ON DELETE SET NULL,
            FOREIGN KEY(source_asset_id) REFERENCES assets(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_conversion_draft_revisions_draft_id
        ON conversion_draft_revisions(draft_id);

        CREATE INDEX IF NOT EXISTS idx_conversion_draft_revisions_saved_config_id
        ON conversion_draft_revisions(saved_config_id);

        CREATE INDEX IF NOT EXISTS idx_conversion_draft_revisions_source_asset_id
        ON conversion_draft_revisions(source_asset_id);

        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            status TEXT NOT NULL,
            target_asset_ids_json TEXT NOT NULL DEFAULT '[]',
            config_json TEXT NOT NULL DEFAULT '{}',
            conversion_run_id TEXT NULL,
            error_message TEXT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT NULL,
            completed_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_created_at
        ON jobs(created_at DESC, id DESC);

        CREATE TABLE IF NOT EXISTS conversion_runs (
            id TEXT PRIMARY KEY,
            job_id TEXT NULL,
            status TEXT NOT NULL,
            source_asset_ids_json TEXT NOT NULL DEFAULT '[]',
            source_asset_paths_json TEXT NOT NULL DEFAULT '[]',
            saved_config_id TEXT NULL,
            saved_config_revision_id TEXT NULL,
            config_json TEXT NOT NULL DEFAULT '{}',
            output_dir TEXT NOT NULL,
            output_paths_json TEXT NOT NULL DEFAULT '[]',
            error_message TEXT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT NULL,
            completed_at TEXT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE SET NULL,
            FOREIGN KEY(saved_config_id) REFERENCES conversion_configs(id) ON DELETE SET NULL,
            FOREIGN KEY(saved_config_revision_id) REFERENCES conversion_config_revisions(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_conversion_runs_created_at
        ON conversion_runs(created_at DESC, id DESC);

        CREATE TABLE IF NOT EXISTS output_artifacts (
            id TEXT PRIMARY KEY,
            conversion_run_id TEXT NULL,
            source_asset_id TEXT NULL,
            source_asset_path TEXT NULL,
            saved_config_id TEXT NULL,
            output_path TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            format TEXT NOT NULL,
            role TEXT NOT NULL,
            media_type TEXT NULL,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            availability_status TEXT NOT NULL DEFAULT 'ready',
            manifest_available INTEGER NOT NULL DEFAULT 0,
            report_available INTEGER NOT NULL DEFAULT 0,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(conversion_run_id) REFERENCES conversion_runs(id) ON DELETE SET NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_output_artifacts_output_path
        ON output_artifacts(output_path);

        CREATE INDEX IF NOT EXISTS idx_assets_registered_at
        ON assets(registered_at DESC, id DESC);

        CREATE INDEX IF NOT EXISTS idx_asset_tags_tag_id
        ON asset_tags(tag_id);
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


def migrate_workspace_schema(connection: sqlite3.Connection, schema_version: int) -> None:
    del connection
    if schema_version == WORKSPACE_SCHEMA_VERSION:
        return

    raise ValueError(
        "unsupported workspace schema version "
        f"{schema_version}; create a fresh local workspace with `hephaes init`"
    )
