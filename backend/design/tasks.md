# Backend Cleanup: Remove Visualization, Episodes, and Backend DB

## Goal

Remove the visualization feature, the episodes/replay feature, and as a result, eliminate the backend's own SQLite database (`app.db`) entirely. After this work:

- All durable state lives exclusively in the hephaes workspace (`workspace.db`)
- The backend has zero SQLAlchemy/ORM dependencies
- The backend has zero rerun-sdk dependency
- The frontend has no replay or visualization UI

---

## Phase 1 — Remove Visualization ✅ COMPLETE

Everything touching `rerun-sdk`, RRD file generation, and visualization job prep.

- [x] Delete `app/api/visualization.py`
- [x] Delete `app/services/visualization.py`
- [x] Delete `app/schemas/visualization.py`
- [x] Delete `tests/test_api_visualization.py`
- [x] `app/main.py` — remove `visualization_router` import and `app.include_router(visualization_router)`
- [x] `app/main.py` — remove `/visualizations` static mount and the `visualizations_dir.mkdir()` call
- [x] `app/config.py` — remove `rerun_sdk_version` and `rerun_recording_format_version` fields from `Settings`
- [x] `app/config.py` — remove `DEFAULT_RERUN_SDK_VERSION`, `DEFAULT_RERUN_RECORDING_FORMAT_VERSION`, `_resolve_rerun_sdk_version()`
- [x] `app/config.py` — remove `app\.rerun\.io` from `DEFAULT_CORS_ALLOW_ORIGIN_REGEX`
- [x] `pyproject.toml` — remove `rerun-sdk` dependency
- [x] `app/services/__init__.py` — remove visualization exports
- [x] `app/schemas/assets.py` — remove `VisualizationSummary` class and `visualization_summary` field from `AssetMetadataResponse`
- [x] `app/mappers/workspace.py` — remove `VisualizationSummary`/`EpisodeSummaryResponse` imports and `map_episode_summary`, `visualization_summary` mapper logic
- [x] `app/api/assets.py` — remove `GET /assets/{asset_id}/episodes` endpoint (cascaded from removing `EpisodeSummaryResponse`), remove `episodes` field from `AssetDetailResponse`

**Also fixed (pre-existing bugs uncovered):**
- `workspace.import_asset()` → `workspace.register_asset()` (method was renamed in hephaes)
- `asset.source_path` removed from `RegisteredAsset` — updated mapper, `_index_workspace_asset`, and `conversions.py` service to use `asset.file_path` directly

**After Phase 1:** `app/services/jobs.py` is dead code (its only caller was visualization). `Job` model has no more writers. Leave both in place until Phase 4.

---

## Phase 2 — Remove Episodes

Everything touching episode playback, timeline scrubbing, and message sampling.

- [ ] Delete `app/api/episodes.py`
- [ ] Delete `app/services/episodes.py`
- [ ] Delete `app/schemas/episodes.py`
- [ ] `app/main.py` — remove `episodes_router` import and `app.include_router(episodes_router)`
- [x] `app/api/assets.py` — remove `GET /assets/{asset_id}/episodes` endpoint *(done in Phase 1 cascade)*
- [x] `app/api/assets.py` — remove `EpisodeSummaryResponse` import and usage *(done in Phase 1 cascade)*
- [x] `app/schemas/assets.py` — remove `EpisodeSummaryResponse` class *(done in Phase 1 cascade)*
- [x] `app/schemas/assets.py` — remove `has_visualizable_streams` and `default_lane_count` from episode-related schemas *(done in Phase 1 cascade)*
- [x] `app/mappers/workspace.py` — remove `map_episode_summary` function *(done in Phase 1 cascade)*
- [x] `app/mappers/workspace.py` — remove `visualization_summary` references from asset mappers *(done in Phase 1 cascade)*
- [ ] `app/services/assets.py` — remove `EpisodeDiscoveryUnavailableError` if it's no longer raised anywhere
- [ ] `pyproject.toml` — remove `websockets` dependency (only used by the episodes replay WebSocket)

---

## Phase 3 — Remove Output Actions

Everything touching the `OutputAction` DB model and the `/actions` sub-routes.

- [ ] `app/api/outputs.py` — remove `POST /outputs/{id}/actions` endpoint (`create_output_action_route`)
- [ ] `app/api/outputs.py` — remove `GET /outputs/{id}/actions` endpoint (`list_output_actions_route`)
- [ ] `app/api/outputs.py` — remove `GET /outputs/actions/{action_id}` endpoint (`get_output_action_route`)
- [ ] `app/api/outputs.py` — remove `output_actions_router` and its single alias endpoint
- [ ] `app/api/outputs.py` — remove `DbSession` dependency, all `session` params from remaining endpoints, `get_latest_output_actions` import and usage
- [ ] `app/api/outputs.py` — remove `latest_action` field from list/detail output responses (set to `None` or remove from schema)
- [ ] `app/main.py` — remove `output_actions_router` import and `app.include_router(output_actions_router)`
- [ ] Delete `app/services/output_actions.py`
- [ ] `app/schemas/outputs.py` — remove `OutputActionCreateRequest`, `OutputActionDetailResponse`, `OutputActionSummaryResponse`
- [ ] `app/schemas/outputs.py` — remove `latest_action` field from `OutputArtifactSummaryResponse` and `OutputArtifactDetailResponse`

**After Phase 3:** `OutputAction` model has no writers. Both DB tables are dead. `app/services/jobs.py` is still dead from Phase 1.

---

## Phase 4 — Remove Backend DB

Eliminate SQLAlchemy, the session factory, and all DB infrastructure.

- [ ] `app/services/dashboard.py` — remove `session: Session` parameter from `get_dashboard_summary`, `get_dashboard_trends`, `get_dashboard_blockers`
- [ ] `app/services/dashboard.py` — remove `_backend_visualization_jobs(session)` function and its call sites (merge step in each function)
- [ ] `app/services/dashboard.py` — remove `from sqlalchemy import select` and `from sqlalchemy.orm import Session` imports
- [ ] `app/services/dashboard.py` — remove `from app.db.models import Job, utc_now` import (keep `utc_now` only if used elsewhere, otherwise inline `datetime.now(UTC)`)
- [ ] `app/api/dashboard.py` — remove `DbSession` dependency from all three route handlers
- [ ] Delete `app/services/jobs.py` (backend Job service, dead since Phase 1)
- [ ] Delete `app/db/models.py`
- [ ] Delete `app/db/session.py`
- [ ] Delete `app/db/` directory
- [ ] `app/main.py` — remove `create_engine_and_session_factory` import and call
- [ ] `app/main.py` — remove `initialize_database(engine)` from lifespan
- [ ] `app/main.py` — remove `app.state.engine`, `app.state.session_factory` assignments
- [ ] `app/main.py` — remove `engine.dispose()` from lifespan teardown
- [ ] `app/config.py` — remove `database_path` and `database_url` fields from `Settings`
- [ ] `app/config.py` — remove `database_path` resolution logic and `database_path.parent.mkdir()` from lifespan (or main)
- [ ] `app/dependencies.py` — remove `get_db_session` dependency if defined there
- [ ] `pyproject.toml` — remove `sqlalchemy` dependency

---

## Phase 5 — Frontend Cleanup

Remove all UI that no longer has a backend counterpart.

- [ ] Remove the Replay/Timeline feature (`frontend/src/features/replay/` or equivalent)
- [ ] Remove visualization prep UI (prepare-visualization button/flow in asset detail)
- [ ] Remove output action UI (action create/list in outputs detail)
- [ ] Remove episode list from asset detail view
- [ ] Remove TypeScript types for removed API shapes: `EpisodeDetailResponse`, `EpisodeTimelineResponse`, `EpisodeSamplesResponse`, `PrepareVisualizationResponse`, `ViewerSourceResponse`, `OutputActionCreateRequest`, `OutputActionDetailResponse`, `OutputActionSummaryResponse`
- [ ] Remove `latest_action` field from output artifact TypeScript types
- [ ] Remove `has_visualizable_streams` and `default_lane_count` from asset TypeScript types
- [ ] Remove Rerun web viewer dependency from `package.json` if present
- [ ] Remove `app.rerun.io` from any frontend CORS or allowed-origin config
