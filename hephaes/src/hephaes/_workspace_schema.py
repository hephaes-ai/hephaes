from __future__ import annotations

import sqlite3

WORKSPACE_DIRNAME = ".hephaes"
WORKSPACE_DB_FILENAME = "workspace.sqlite3"
WORKSPACE_SCHEMA_VERSION = 2


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
            (str(WORKSPACE_SCHEMA_VERSION),),
        )
        return

    raise ValueError(
        "workspace schema version mismatch: "
        f"expected {WORKSPACE_SCHEMA_VERSION}, got {schema_version}"
    )
