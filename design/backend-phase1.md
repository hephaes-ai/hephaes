# Backend Phase 1

## Goal

Build the first working local backend slice with:

- `hephaes` as the reusable installable core package
- `backend/` as the FastAPI app
- SQLite as the local persistence layer
- a local asset registry for files on disk

Phase 1 is intentionally narrow. It is about getting assets into the app and making them queryable by the frontend.

For this phase, use file-path registration as the ingestion mechanism because it is the simplest way to get the backend and SQLite working end to end. Upload-based ingestion can be added later.

## Repository Shape

```text
repo/
  pyproject.toml
  src/hephaes/
  backend/
    app/
      __init__.py
      main.py
      config.py
      api/
      db/
      schemas/
      services/
    tests/
  frontend/
  design/
```

The root `pyproject.toml` remains the only Python project file. The installable package is still only `hephaes` from `src/hephaes/`. The `backend/` folder is app code, not a separately packaged distribution.

## Packaging and Dependencies

Keep the core library and the backend in one Python project for now:

- `pip install .` installs the `hephaes` package and core dependencies
- `pip install ".[backend]"` installs `hephaes` plus backend dependencies
- `pip install -e ".[dev,backend]"` is the preferred local development setup

Recommended backend dependencies for this phase:

- `fastapi`
- `uvicorn`
- `sqlalchemy`

SQLite does not need an extra package for the sync path because Python already includes `sqlite3`.

## Responsibilities

### `src/hephaes/`

Keep this package reusable and installable on its own. It should contain:

- file inspection helpers that are useful outside the app
- shared domain models
- future indexing or conversion logic that is not tied to HTTP or SQLite

Do not put these here:

- FastAPI routes
- database models for the app
- request and response models that only exist for the web API

### `backend/`

This is the local application layer. It should own:

- FastAPI app setup
- SQLite access
- the asset registry table
- route handlers
- service logic that calls into `hephaes`

## Asset Registry Schema

Create an `assets` table with these fields:

- `id`: UUID string primary key
- `file_path`: unique absolute path
- `file_name`
- `file_type`
- `file_size`
- `registered_time`
- `indexing_status`
- `last_indexed_time`

Recommended status values:

- `pending`
- `indexing`
- `indexed`
- `failed`

Recommended constraints:

- unique index on `file_path`
- non-null constraints on required fields
- `file_size >= 0`

## Backend Structure

Suggested layout:

```text
backend/app/
  __init__.py
  main.py
  config.py
  db/
    session.py
    models.py
  api/
    assets.py
  schemas/
    assets.py
  services/
    assets.py
```

Suggested roles:

- `main.py`: create the FastAPI app and register routes
- `config.py`: database file path and local settings
- `db/models.py`: SQLAlchemy models
- `db/session.py`: engine and session setup
- `api/assets.py`: asset routes
- `schemas/assets.py`: Pydantic request and response models
- `services/assets.py`: asset registration and retrieval logic

## Core Flows

### Asset registration

Input:

- file path from the frontend

Behavior:

- normalize to an absolute path
- verify the file exists
- read file metadata from disk
- derive `file_name`
- derive `file_type`
- derive `file_size`
- create an `assets` row with `indexing_status = "pending"`
- reject duplicate `file_path` values cleanly

### Asset retrieval

Behavior:

- list all assets
- fetch one asset by `id`

Phase 1 does not need full search, metadata extraction, tags, upload handling, or jobs yet.

## API Surface

Implement these routes in phase 1:

- `GET /health`
- `POST /assets/register`
- `GET /assets`
- `GET /assets/{asset_id}`

Suggested request for `POST /assets/register`:

```json
{
  "file_path": "/absolute/path/to/file.mcap"
}
```

Suggested response shape:

```json
{
  "id": "uuid",
  "file_path": "/absolute/path/to/file.mcap",
  "file_name": "file.mcap",
  "file_type": "mcap",
  "file_size": 123456,
  "registered_time": "2026-03-14T10:00:00Z",
  "indexing_status": "pending",
  "last_indexed_time": null
}
```

## Deliverable

By the end of phase 1, you should be able to:

- run the FastAPI server locally
- connect to a SQLite database file
- create the `assets` table
- register local files by path
- list registered assets
- fetch an asset detail record

## Implementation Order

1. Add `backend` optional dependencies to the root `pyproject.toml`.
2. Create the `backend/` app structure.
3. Add SQLite engine and session wiring.
4. Define the `assets` model.
5. Implement `GET /health`.
6. Implement `POST /assets/register`.
7. Implement `GET /assets`.
8. Implement `GET /assets/{asset_id}`.
9. Add backend tests for registration, duplicates, and retrieval.

## Tasks

### Project setup

- Add a `backend` optional dependency group in [pyproject.toml](/Users/danielyoo/workspace/hephaes/pyproject.toml) with `fastapi`, `uvicorn`, and `sqlalchemy`.
- Decide on the local backend entrypoint command, likely `uvicorn backend.app.main:app --reload`.
- Create the backend directory structure under `backend/app/` and `backend/tests/`.
- Add `__init__.py` files where needed so backend imports are clean and explicit.

### App bootstrap

- Create [backend/app/main.py](/Users/danielyoo/workspace/hephaes/backend/app/main.py) with FastAPI app initialization.
- Create [backend/app/config.py](/Users/danielyoo/workspace/hephaes/backend/app/config.py) for local settings such as SQLite database path.
- Add a `GET /health` route that returns a simple success response.
- Confirm the backend starts locally and serves the health endpoint.

### Database foundation

- Create [backend/app/db/session.py](/Users/danielyoo/workspace/hephaes/backend/app/db/session.py) to configure the SQLAlchemy engine and session factory.
- Decide where the SQLite file should live, such as `backend/data/app.db`.
- Add initialization logic that creates tables for the MVP.
- Ensure the database path is created safely if parent directories do not exist.

### Asset model

- Create [backend/app/db/models.py](/Users/danielyoo/workspace/hephaes/backend/app/db/models.py) with the `assets` table definition.
- Define the `id`, `file_path`, `file_name`, `file_type`, `file_size`, `registered_time`, `indexing_status`, and `last_indexed_time` columns.
- Add a uniqueness constraint on `file_path`.
- Add a `file_size >= 0` constraint if practical in the chosen SQLAlchemy model style.

### API schemas

- Create [backend/app/schemas/assets.py](/Users/danielyoo/workspace/hephaes/backend/app/schemas/assets.py) with request and response models.
- Add a registration request schema with `file_path`.
- Add response schemas for asset list items and asset detail responses.
- Keep schema names specific enough that later metadata and tag fields can be added cleanly.

### Asset service

- Create [backend/app/services/assets.py](/Users/danielyoo/workspace/hephaes/backend/app/services/assets.py) for business logic.
- Implement path normalization to absolute paths.
- Validate that the requested file exists and is a file, not a directory.
- Read file stats from disk and derive `file_name`, `file_type`, and `file_size`.
- Insert a new asset row with `indexing_status = "pending"`.
- Detect duplicate registrations and return a clear application-level error.
- Implement retrieval helpers for listing assets and fetching one asset by ID.

### Asset routes

- Create [backend/app/api/assets.py](/Users/danielyoo/workspace/hephaes/backend/app/api/assets.py).
- Implement `POST /assets/register`.
- Implement `GET /assets`.
- Implement `GET /assets/{asset_id}`.
- Map service errors to appropriate HTTP responses such as `404` for missing assets and `409` for duplicate registration.

### Local verification

- Start the backend locally and verify `GET /health`.
- Register a real test file from the local filesystem with `POST /assets/register`.
- Verify the returned asset fields match the file on disk.
- Call `GET /assets` and confirm the new asset appears.
- Call `GET /assets/{asset_id}` and confirm detail lookup works.

### Tests

- Add backend tests under `backend/tests/`.
- Add a test for successful file registration using a temporary file.
- Add a test for duplicate path registration.
- Add a test for a missing file path.
- Add a test for `GET /assets`.
- Add a test for `GET /assets/{asset_id}` with both existing and missing IDs.

### Nice-to-have cleanup

- Add a short README or developer note for how to run the backend locally.
- Add logging around asset registration failures to make local debugging easier.
- Decide whether table creation should happen automatically on startup or through a small explicit init step.
