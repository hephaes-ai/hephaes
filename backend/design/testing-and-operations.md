# Testing And Operations

## Local Development Workflow

The backend is currently operated as a straightforward local FastAPI app.

### Install

From `backend/`:

```bash
python -m pip install -e ../hephaes
python -m pip install -e ".[dev]"
```

Replay websocket support depends on the backend install including a websocket
transport library. Reinstall the backend package after pulling dependency
changes so `websockets` is available in the active environment.

### Run

From `backend/`:

```bash
python -m uvicorn app.main:app --reload
```

### Test

From `backend/`:

```bash
pytest tests -q
```

## Environment Variables

The current backend reads several environment variables through `get_settings()`.

Common ones:

- `HEPHAES_BACKEND_APP_NAME`
- `HEPHAES_BACKEND_DEBUG`
- `HEPHAES_BACKEND_DATA_DIR`
- `HEPHAES_BACKEND_RAW_DATA_DIR`
- `HEPHAES_BACKEND_OUTPUTS_DIR`
- `HEPHAES_BACKEND_DB_PATH`
- `HEPHAES_RERUN_SDK_VERSION`
- `HEPHAES_RERUN_RECORDING_FORMAT_VERSION`

Tests rely heavily on these path overrides so each run uses a temporary database and output tree.

## Test Structure

Tests live under `backend/tests/` and are mostly API-level tests built with FastAPI `TestClient`.

### Shared fixture design

`tests/conftest.py` creates temporary paths for:

- the SQLite database
- raw upload storage
- outputs

It also clears the cached settings object before and after each test client session so environment overrides are respected.

### Covered behavior areas

The current suite covers:

- health and basic asset registration
- duplicate-path rejection
- native dialog integration behavior
- asset listing order and filtering
- asset detail loading
- indexing success and failure paths
- durable job creation and ordering
- tag creation, duplicate handling, attach, remove, and filtering
- uploads and directory scanning
- episode detail, timeline, and sample APIs
- conversion success and failure flows
- visualization preparation, cache reuse, version metadata, stale artifact invalidation, and static artifact serving

## Testing Style

The backend tests lean on monkeypatching to isolate the app from heavy external work while still exercising real HTTP routes.

Common patterns:

- patch `profile_asset_file()` instead of running the real profiler
- patch `open_asset_reader()` with fake message readers for playback tests
- patch `Converter` for conversion tests
- patch `_generate_rrd()` for visualization tests

That gives the suite stable, local, end-to-end route coverage without depending on real ROS bag parsing for every test.

## Operational Notes

### CORS

The app allows HTTP origins matching:

- `localhost`
- `127.0.0.1`
- `app.rerun.io`

This supports local frontend development and Rerun viewer interaction.

### Static artifacts

Visualization artifacts are served directly by FastAPI through a `StaticFiles` mount. This is simple and useful for local development, though it is not a production CDN-style serving model.

### Database lifecycle

The app currently initializes tables with `Base.metadata.create_all()`. There is no Alembic migration workflow yet.

### Job execution

Jobs are durable in the database but still executed inline during the request that creates them. That means:

- the frontend can inspect durable status history
- the backend remains simple
- long-running work still occupies the API process during execution

## Current Constraints And Future Pressure Points

A few current implementation limits are worth documenting explicitly.

### Persistence limits

- no migration framework
- no separate episode or stream tables
- JSON-heavy metadata and workflow config storage

### Execution limits

- no worker queue or background executor
- indexing, conversion, and visualization prep all run inline

### Querying limits

- some related-record lookups are broad queries filtered in Python
- the schema is optimized for a small local dataset rather than large-scale analytics

### Playback limits

- episode support is currently centered on a single derived default episode
- playback APIs reread asset files directly instead of serving from a precomputed event store

### Visualization limits

- Rerun generation is intentionally narrow in the payload types it logs richly
- cache validation is file-and-sidecar based rather than database-backed

None of these are blockers for the current local product shape, but they are the main areas that would need attention if the backend grows beyond the current single-user local workflow.
