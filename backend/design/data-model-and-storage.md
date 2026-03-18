# Data Model And Storage

## Persistence Overview

The backend stores durable state in one SQLite database plus a small set of backend-owned directories on disk.

Current storage responsibilities are split like this:

- SQLite stores assets, indexed metadata, tags, jobs, and conversion records
- `data/raw/` stores uploaded asset files
- `data/outputs/` stores conversion and visualization artifacts

## Database Tables

The SQLAlchemy models live in `app/db/models.py`.

### `assets`

The `assets` table is the backbone of the app.

Important fields:

- `id`
- `file_path`
- `file_name`
- `file_type`
- `file_size`
- `registered_time`
- `indexing_status`
- `last_indexed_time`

Constraints:

- unique `file_path`
- non-negative `file_size`
- `indexing_status` limited to `pending | indexing | indexed | failed`

Relationships:

- one-to-one with `asset_metadata`
- many-to-many with `tags`

### `asset_metadata`

Indexed metadata is stored in a separate table keyed by `asset_id`.

Important fields:

- `duration`
- `start_time`
- `end_time`
- `topic_count`
- `message_count`
- `sensor_types_json`
- `topics_json`
- `default_episode_json`
- `visualization_summary_json`
- `raw_metadata_json`
- `indexing_error`
- `created_at`
- `updated_at`

This table is the bridge between raw asset registration and higher-order workflows like replay, filtering, and conversion.

### `tags`

Tags are lightweight labels with:

- `id`
- `name`
- `normalized_name`
- `created_at`

`normalized_name` is unique so tag names are case-insensitive in practice.

### `asset_tags`

The asset-tag join table provides many-to-many tagging and cascades deletes from either side.

### `jobs`

The `jobs` table stores durable workflow history for:

- indexing
- conversion
- visualization preparation

Important fields:

- `type`
- `status`
- `target_asset_ids_json`
- `config_json`
- `output_path`
- `error_message`
- `created_at`
- `updated_at`
- `started_at`
- `finished_at`

The current implementation uses jobs as durable workflow records even though execution still happens inline.

### `conversions`

Conversion runs are stored separately from jobs so the API can expose conversion-specific output metadata without overloading the jobs table.

Important fields:

- `id`
- `job_id`
- `status`
- `source_asset_ids_json`
- `config_json`
- `output_path`
- `output_files_json`
- `error_message`
- `created_at`
- `updated_at`

Each conversion is linked one-to-one to a job by a unique `job_id`.

## Modeling Strategy

The backend intentionally uses JSON columns in several places instead of fully normalizing every concept into new tables.

### JSON-backed structures

Current JSON payloads include:

- indexed topic summaries
- sensor types
- default episode summary
- visualization readiness summary
- raw profiler metadata
- job config
- conversion config
- conversion output files

This has a few practical benefits for the current stage:

- easier iteration while API contracts are still evolving
- fewer migrations while the product shape is still changing
- direct reuse of structured outputs from `hephaes`

The tradeoff is that some filtering and data integrity rules live in service code rather than in strongly normalized relational tables.

## No Episode Tables Yet

One important current design choice is that episodes are not stored as their own rows.

Instead, the backend derives episode data from:

- indexed asset metadata
- raw file headers and message reads through `RosReader`

Today that results in a single default episode per indexed asset:

- `episode_id = "{asset_id}:default"`
- `label = "Episode 1"`

That is enough to support replay APIs now while keeping the persistent model smaller.

## Filesystem Layout

### SQLite database

Default location:

- `backend/data/app.db`

### Uploaded raw assets

Uploads are written into:

- `backend/data/raw/`

The stored file name comes from the `X-File-Name` header after normalization and validation.

### Conversion outputs

Each conversion gets its own output directory:

- `backend/data/outputs/conversions/<conversion_id>/`

The conversion record and linked job both point at that output path.

### Visualization outputs

Prepared Rerun artifacts are written into:

- `backend/data/outputs/visualizations/<asset_id>/<episode_id>/recording.rrd`
- `backend/data/outputs/visualizations/<asset_id>/<episode_id>/recording.meta.json`

The `.meta.json` sidecar is used to validate cached artifacts against the current viewer and recording version expectations.

## Output Serving

`app/main.py` mounts:

- `/visualizations`

as a static file tree backed by `outputs/visualizations`.

That means the frontend never needs to know real filesystem paths to load prepared viewer artifacts. It only consumes backend-generated URLs like:

- `/visualizations/<asset_id>/<episode_id>/recording.rrd`

## Session And Initialization

`app/db/session.py` handles:

- engine creation
- session factory creation
- directory creation for the database file
- dependency injection of database sessions into FastAPI routes

The session factory uses:

- `autoflush=False`
- `autocommit=False`
- `expire_on_commit=False`

which makes service-layer object reuse simpler during a single request flow.

## Current Data-Layer Tradeoffs

The current storage design favors fast local iteration over heavy infrastructure:

- simple SQLite setup instead of a larger database stack
- `create_all` instead of migrations
- JSON columns instead of fully normalized playback and workflow tables
- artifact metadata sidecars instead of a dedicated visualization-artifact table

That keeps the storage model understandable and easy to reset while still supporting the current frontend features.
