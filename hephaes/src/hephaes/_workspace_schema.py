from __future__ import annotations

import sqlite3

WORKSPACE_DIRNAME = ".hephaes"
WORKSPACE_DB_FILENAME = "workspace.sqlite3"
WORKSPACE_SCHEMA_VERSION = 6


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
            source_path TEXT NULL UNIQUE,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            indexing_status TEXT NOT NULL DEFAULT 'pending',
            last_indexed_at TEXT NULL,
            imported_at TEXT NOT NULL,
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

        CREATE TABLE IF NOT EXISTS output_artifacts (
            id TEXT PRIMARY KEY,
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
            updated_at TEXT NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_output_artifacts_output_path
        ON output_artifacts(output_path);

        CREATE INDEX IF NOT EXISTS idx_assets_registered_at
        ON assets(registered_at DESC, id DESC);

        CREATE INDEX IF NOT EXISTS idx_assets_source_path
        ON assets(source_path);

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
            ("2",),
        )
        schema_version = 2

    if schema_version == 2:
        connection.execute(
            """
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
            )
            """
        )
        connection.execute(
            "UPDATE workspace_meta SET value = ? WHERE key = 'schema_version'",
            ("3",),
        )
        schema_version = 3

    if schema_version == 3:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS output_artifacts (
                id TEXT PRIMARY KEY,
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
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_output_artifacts_output_path
            ON output_artifacts(output_path)
            """
        )
        connection.execute(
            "UPDATE workspace_meta SET value = ? WHERE key = 'schema_version'",
            ("4",),
        )
        schema_version = 4
    if schema_version == 4:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(assets)").fetchall()
        }
        if "source_path" not in columns:
            connection.execute("ALTER TABLE assets ADD COLUMN source_path TEXT NULL")
        if "imported_at" not in columns:
            connection.execute("ALTER TABLE assets ADD COLUMN imported_at TEXT NULL")
            connection.execute(
                """
                UPDATE assets
                SET imported_at = COALESCE(registered_at, updated_at)
                WHERE imported_at IS NULL
                """
            )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_assets_source_path
            ON assets(source_path)
            WHERE source_path IS NOT NULL
            """
        )
        connection.execute(
            "UPDATE workspace_meta SET value = ? WHERE key = 'schema_version'",
            ("5",),
        )
        schema_version = 5
    if schema_version == 5:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tags (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                normalized_name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS asset_tags (
                asset_id TEXT NOT NULL,
                tag_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(asset_id, tag_id),
                FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE,
                FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_asset_tags_tag_id
            ON asset_tags(tag_id)
            """
        )
        connection.execute(
            "UPDATE workspace_meta SET value = ? WHERE key = 'schema_version'",
            (str(WORKSPACE_SCHEMA_VERSION),),
        )
        return

    raise ValueError(
        "workspace schema version mismatch: "
        f"expected {WORKSPACE_SCHEMA_VERSION}, got {schema_version}"
    )
