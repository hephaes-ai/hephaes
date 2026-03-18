# Backend Architecture

## Purpose

The backend is a local FastAPI application that manages registered ROS bag assets, indexed metadata, durable workflow records, conversion outputs, playback-oriented episode APIs, and prepared Rerun viewer artifacts.

It is designed for a local desktop workflow:

- files live on local disk
- SQLite is the only database
- outputs are written to backend-owned directories
- durable jobs exist as records in the database, but execution is currently inline in the API process

## Stack

The live backend stack is defined in `backend/pyproject.toml` and implemented under `backend/app/`.

- FastAPI for HTTP routing
- SQLAlchemy 2 for ORM and session management
- SQLite for local persistence
- Pydantic for request and response contracts
- `hephaes` as the reusable profiling, reading, and conversion core package
- `rerun-sdk` for visualization artifact generation
- pytest plus FastAPI `TestClient` for test coverage

## App Bootstrap

`app/main.py` is the composition root.

### Application setup

`create_app()` does the following:

- resolves settings from `app/config.py`
- creates the SQLAlchemy engine and session factory
- installs a lifespan handler that creates local data directories and initializes tables
- stores `settings`, `engine`, and `session_factory` on `app.state`
- registers all routers
- mounts `/visualizations` as a static directory backed by `outputs/visualizations`

### Lifespan behavior

At startup the app ensures these directories exist:

- `data/`
- `data/raw/`
- `data/outputs/`

It then runs `Base.metadata.create_all(bind=engine)`.

There is no migration tool or separate schema bootstrap process yet. The current design assumes a local developer database that can be created on demand.

## Configuration Model

`app/config.py` exposes a cached `Settings` dataclass.

Important settings include:

- app name
- debug flag
- repo root and backend dir
- `data_dir`
- `raw_data_dir`
- `outputs_dir`
- `database_path`
- `database_url`
- `rerun_sdk_version`
- `rerun_recording_format_version`

Environment variables let the backend redirect data, raw uploads, outputs, and the SQLite database into test or local override directories.

## Module Boundaries

The backend is organized by layer.

### `app/api/`

Routers translate HTTP concerns into service calls:

- parse query params and headers
- validate payloads
- map domain exceptions to HTTP status codes
- serialize service/domain objects into response schemas

Routers are intentionally thin.

### `app/services/`

Services own application behavior:

- asset registration, upload, directory scan, and listing
- indexing and metadata persistence
- tag creation and attachment rules
- durable job creation and state transitions
- conversion execution
- playback-oriented episode/timeline/sample extraction
- visualization artifact preparation and viewer-source manifests

### `app/db/`

The database layer defines SQLAlchemy models and session helpers. It does not contain business logic beyond constraints and relationships.

### `app/schemas/`

The schema layer is the public API contract:

- request validation
- response serialization
- UTC normalization
- strict payload shape enforcement with `extra="forbid"`

## Execution Model

The current backend is synchronous and single-process in spirit.

### Durable-but-inline jobs

Jobs are persisted in the `jobs` table and exposed through `/jobs`, but actual work is still executed inline during API requests:

- indexing runs inside the `/assets/{asset_id}/index` request
- conversions run inside `POST /conversions`
- visualization preparation runs inside `POST /prepare-visualization`

This gives the frontend durable status and history today without introducing a queue, workers, or external orchestration yet.

### File-backed workflows

The backend treats files as the source of truth:

- registered asset paths point at files on disk
- uploads are written to `data/raw/`
- conversions write files into `data/outputs/conversions/`
- visualization prep writes `.rrd` artifacts into `data/outputs/visualizations/`

## Routing Structure

The routers are grouped by domain:

- `health.py`
- `assets.py`
- `episodes.py`
- `conversions.py`
- `jobs.py`
- `tags.py`
- `visualization.py`

This keeps the public API aligned with user-facing workflows rather than with database tables alone.

## Cross-Cutting Design Choices

### Close to the frontend contract

The backend stores enough durable data to let the frontend render rich views, but many responses are still assembled dynamically from multiple sources:

- asset detail combines asset row, metadata row, tags, derived episodes, related jobs, and related conversions
- viewer-source manifests combine job state plus artifact existence and version metadata

### JSON-heavy persistence

Instead of fully normalizing topics, episodes, mappings, or output manifests into separate tables, the current design stores structured JSON in a few strategic places:

- indexed metadata topics
- visualization summaries
- job config
- conversion config
- conversion output file lists

That keeps iteration fast while the product surface is still evolving.

### Local-first assumptions

The app is optimized for local use, not multi-tenant deployment:

- SQLite with `check_same_thread=False`
- permissive localhost and `app.rerun.io` CORS rules
- direct local filesystem access
- static artifact serving from a backend-owned directory

## Current Architectural Tradeoffs

A few important tradeoffs are visible in the implementation:

- jobs are durable records, but not truly asynchronous yet
- there is no migration layer beyond `create_all`
- episodes are derived from indexed metadata and raw file rereads rather than stored as first-class rows
- some relationship lookups, like related jobs and conversions for an asset, are currently filtered in Python after broad queries instead of through highly targeted SQL

Those choices keep the codebase compact and understandable while the product is still proving out its local workflow model.
