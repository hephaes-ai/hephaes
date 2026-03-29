# Backend Current State

Snapshot of the backend as of the start of the visualization/episodes/DB removal effort.

---

## Overview

The backend is a FastAPI sidecar process that Tauri spawns and polls. It serves as a thin HTTP adapter between the frontend and the hephaes Python library. State lives in two places:

- **hephaes workspace** (`workspace.db`) — assets, conversions, configs, drafts, jobs, output artifacts
- **backend DB** (`app.db`) — `Job` records (only visualization jobs) and `OutputAction` records

The goal of this effort is to remove the visualization feature, the episodes/replay feature, and as a result, eliminate the backend DB entirely.

---

## File Inventory

### `app/api/` — Route handlers

| File | Endpoints | Uses DB? | Status |
|------|-----------|----------|--------|
| `assets.py` | GET/POST /assets, POST /assets/register, POST /assets/upload, POST /assets/scan-directory, POST /assets/{id}/index, POST/DELETE /assets/{id}/tags, POST /assets/reindex-all, GET /assets/{id}/episodes | No | Keep, remove episodes endpoint |
| `episodes.py` | GET /assets/{id}/episodes/{eid}, GET .../timeline, GET .../samples, WS .../replay | No | **Remove entirely** |
| `visualization.py` | POST .../prepare-visualization, GET .../viewer-source | Yes | **Remove entirely** |
| `conversions.py` | POST /conversions, GET /conversions/capabilities, POST /conversions/inspect, POST /conversions/draft, POST /conversions/preview, GET /conversions, GET /conversions/{id} | No | Keep |
| `conversion_configs.py` | GET/POST /conversion-configs, GET/PATCH/POST /conversion-configs/{id} | No | Keep |
| `jobs.py` | GET /jobs, GET /jobs/{id} | No | Keep (queries workspace jobs, not DB) |
| `outputs.py` | GET/GET-detail /outputs, GET /outputs/{id}/content, POST/GET /outputs/{id}/actions, GET /outputs/actions/{id}, GET /output-actions/{id} | Yes (action endpoints only) | Keep, remove action endpoints |
| `tags.py` | GET /tags, POST /tags | No | Keep |
| `dashboard.py` | GET /dashboard/summary, GET /dashboard/trends, GET /dashboard/blockers | Yes | Keep, remove session dependency |
| `health.py` | GET /health | No | Keep |

### `app/services/` — Business logic

| File | Purpose | Uses DB? | Status |
|------|---------|----------|--------|
| `assets.py` | Path normalization, file dialogs, directory scanning | No | Keep |
| `episodes.py` | Episode detail, timeline bucketing, message sampling for replay | No | **Remove entirely** |
| `visualization.py` | RRD generation via rerun-sdk, prepare-visualization job orchestration | Yes (Job model) | **Remove entirely** |
| `jobs.py` | CRUD for backend `Job` DB model | Yes (Job model) | **Remove entirely** (only used by visualization) |
| `conversions.py` | Conversion creation and execution, delegates to workspace | No | Keep |
| `conversion_authoring.py` | Inspect/draft/preview workflow, delegates to workspace | No | Keep |
| `output_actions.py` | OutputAction CRUD (refresh_metadata action type) | Yes (OutputAction model) | **Remove entirely** |
| `dashboard.py` | Aggregate stats from workspace + backend DB | Yes (visualization jobs only) | Keep, remove `session` param and `_backend_visualization_jobs()` |
| `indexing.py` | Thin wrapper around hephaes Profiler | No | Keep |
| `job_runner.py` | ThreadPoolExecutor wrapper for background jobs | No | Keep |

### `app/schemas/` — Pydantic response/request models

| File | Status |
|------|--------|
| `assets.py` | Keep, remove `EpisodeSummaryResponse`, remove `has_visualizable_streams`/`default_lane_count` fields |
| `episodes.py` | **Remove entirely** |
| `visualization.py` | **Remove entirely** |
| `conversions.py` | Keep |
| `conversion_authoring.py` | Keep |
| `jobs.py` | Keep (represents workspace jobs, not DB jobs) |
| `outputs.py` | Keep, remove `OutputActionCreateRequest`, `OutputActionDetailResponse`, `OutputActionSummaryResponse`, remove `latest_action` field from artifact responses |
| `dashboard.py` | Keep (no change needed to schemas themselves) |

### `app/db/` — SQLAlchemy ORM

| File | Contents | Status |
|------|----------|--------|
| `models.py` | `Job` model (type: prepare_visualization, index, convert — only viz used), `OutputAction` model | **Remove entirely** |
| `session.py` | Engine creation, `get_db_session` dependency | **Remove entirely** |

### Other files

| File | Status |
|------|--------|
| `main.py` | Remove: episodes router, visualization router, output_actions_router, `/visualizations` static mount, DB engine/session init, `initialize_database()` call |
| `config.py` | Remove: `database_path`, `database_url`, `rerun_sdk_version`, `rerun_recording_format_version`, `_resolve_rerun_sdk_version()`, `DEFAULT_RERUN_*` constants. Remove `app.rerun.io` from default CORS regex |
| `dependencies.py` | Remove `get_db_session` if defined here (currently in `app/db/session.py`) |
| `workspace_bootstrap.py` | Keep, no changes needed |
| `desktop_main.py` | Keep, no changes needed |
| `mappers/workspace.py` | Remove `map_episode_summary`, remove visualization_summary fields from asset mappers |

### `pyproject.toml` dependencies

| Dependency | Status |
|-----------|--------|
| `fastapi` | Keep |
| `uvicorn` | Keep |
| `websockets` | **Remove** (only used by episodes replay WebSocket) |
| `sqlalchemy` | **Remove** |
| `rerun-sdk` | **Remove** |
| `hephaes` | Keep |

---

## DB Dependency Map

The backend's `app.db` SQLite file has two tables:

### `jobs` table
- **Writers:** `app/services/visualization.py` via `JobService`
- **Readers:** `app/services/dashboard.py` (`_backend_visualization_jobs`), `app/services/jobs.py`
- **Routes:** `app/api/visualization.py` (create/read), `app/api/dashboard.py` (read)
- **After removing visualization:** zero writers, dashboard reads become no-ops → table is dead

### `output_actions` table
- **Writers:** `app/services/output_actions.py` (`OutputActionService.create_action`)
- **Readers:** `app/services/output_actions.py` (query helpers), `app/api/outputs.py` (list/get actions)
- **Routes:** `POST /outputs/{id}/actions`, `GET /outputs/{id}/actions`, `GET /output-actions/{id}`
- **After removing output actions:** table is dead

Once both tables have no writers, the entire `app.db` is dead weight.

---

## CORS Note

Current default allows `app.rerun.io` (for the Rerun web viewer). After removing visualization this origin can be removed.

Default: `r"https?://(localhost|127\.0\.0\.1|app\.rerun\.io)(:\d+)?"`
Target: `r"https?://(localhost|127\.0\.0\.1)(:\d+)?"`
