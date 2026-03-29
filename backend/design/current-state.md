# Backend Current State

Snapshot of the backend after completing Phases 1–4 (Visualization, Episodes, Output Actions, Backend DB all removed).

---

## Overview

The backend is a FastAPI sidecar process that Tauri spawns and polls. It serves as a thin HTTP adapter between the frontend and the hephaes Python library.

**All durable state now lives exclusively in the hephaes workspace (`workspace.db`).** The backend has zero SQLAlchemy/ORM dependencies.

---

## File Inventory

### `app/api/` — Route handlers

| File | Endpoints | Status |
|------|-----------|--------|
| `assets.py` | GET/POST /assets, POST /assets/register, POST /assets/upload, POST /assets/scan-directory, POST /assets/{id}/index, POST/DELETE /assets/{id}/tags, POST /assets/reindex-all | ✅ Keep |
| `episodes.py` | — | ✅ **Deleted (Phase 2)** |
| `visualization.py` | — | ✅ **Deleted (Phase 1)** |
| `conversions.py` | POST /conversions, GET /conversions/capabilities, POST /conversions/inspect, POST /conversions/draft, POST /conversions/preview, GET /conversions, GET /conversions/{id} | ✅ Keep |
| `conversion_configs.py` | GET/POST /conversion-configs, GET/PATCH/POST /conversion-configs/{id} | ✅ Keep |
| `jobs.py` | GET /jobs, GET /jobs/{id} | ✅ Keep (workspace jobs only) |
| `outputs.py` | GET/GET-detail /outputs, GET /outputs/{id}/content | ✅ Keep (action endpoints removed Phase 3) |
| `tags.py` | GET /tags, POST /tags | ✅ Keep |
| `dashboard.py` | GET /dashboard/summary, GET /dashboard/trends, GET /dashboard/blockers | ✅ Keep (session removed Phase 4) |
| `health.py` | GET /health | ✅ Keep |

### `app/services/` — Business logic

| File | Purpose | Status |
|------|---------|--------|
| `assets.py` | Path normalization, file dialogs, directory scanning | ✅ Keep |
| `episodes.py` | — | ✅ **Deleted (Phase 2)** |
| `visualization.py` | — | ✅ **Deleted (Phase 1)** |
| `jobs.py` | — | ✅ **Deleted (Phase 4)** |
| `conversions.py` | Conversion creation and execution, delegates to workspace | ✅ Keep |
| `conversion_authoring.py` | Inspect/draft/preview workflow, delegates to workspace | ✅ Keep |
| `output_actions.py` | — | ✅ **Deleted (Phase 3)** |
| `dashboard.py` | Aggregate stats from workspace only | ✅ Keep (session removed Phase 4) |
| `indexing.py` | Thin wrapper around hephaes Profiler | ✅ Keep |
| `job_runner.py` | ThreadPoolExecutor wrapper for background jobs | ✅ Keep |

### `app/schemas/` — Pydantic response/request models

| File | Status |
|------|--------|
| `assets.py` | ✅ Keep |
| `episodes.py` | ✅ **Deleted (Phase 2)** |
| `visualization.py` | ✅ **Deleted (Phase 1)** |
| `conversions.py` | ✅ Keep |
| `conversion_authoring.py` | ✅ Keep |
| `jobs.py` | ✅ Keep (workspace jobs) |
| `outputs.py` | ✅ Keep (`OutputAction*` schemas removed Phase 3) |
| `dashboard.py` | ✅ Keep |

### `app/db/` — SQLAlchemy ORM

✅ **Entire directory deleted (Phase 4).** `models.py`, `session.py`, `__init__.py` all removed.

### Other files

| File | Status |
|------|--------|
| `main.py` | ✅ Cleaned — no DB engine/session, no viz/episodes routers |
| `config.py` | ✅ Cleaned — no `database_path`/`database_url`, no rerun fields |
| `dependencies.py` | ✅ Cleaned — `get_db_session` removed |
| `workspace_bootstrap.py` | ✅ Keep, no changes |
| `desktop_main.py` | ✅ Keep, no changes |
| `mappers/workspace.py` | ✅ Cleaned — viz/episode mapper logic removed |

### `pyproject.toml` dependencies

| Dependency | Status |
|-----------|--------|
| `fastapi` | ✅ Keep |
| `uvicorn` | ✅ Keep |
| `websockets` | ✅ **Removed (Phase 2)** |
| `sqlalchemy` | ✅ **Removed (Phase 4)** |
| `rerun-sdk` | ✅ **Removed (Phase 1)** |
| `hephaes` | ✅ Keep |

---

## CORS Note

✅ `app.rerun.io` removed from CORS regex in Phase 1.

Current: `r"https?://(localhost|127\.0\.0\.1)(:\d+)?"`
