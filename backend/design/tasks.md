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

## Phase 2 — Remove Episodes ✅ COMPLETE

Everything touching episode playback, timeline scrubbing, and message sampling.

- [x] Delete `app/api/episodes.py`
- [x] Delete `app/services/episodes.py`
- [x] Delete `app/schemas/episodes.py`
- [x] Delete `tests/test_api_episodes.py`
- [x] `app/main.py` — remove `episodes_router` import and `app.include_router(episodes_router)`
- [x] `app/api/assets.py` — remove `GET /assets/{asset_id}/episodes` endpoint *(done in Phase 1 cascade)*
- [x] `app/api/assets.py` — remove `EpisodeSummaryResponse` import and usage *(done in Phase 1 cascade)*
- [x] `app/schemas/assets.py` — remove `EpisodeSummaryResponse` class *(done in Phase 1 cascade)*
- [x] `app/schemas/assets.py` — remove `has_visualizable_streams` and `default_lane_count` from episode-related schemas *(done in Phase 1 cascade)*
- [x] `app/mappers/workspace.py` — remove `map_episode_summary` function *(done in Phase 1 cascade)*
- [x] `app/mappers/workspace.py` — remove `visualization_summary` references from asset mappers *(done in Phase 1 cascade)*
- [x] `app/services/assets.py` — remove `EpisodeDiscoveryUnavailableError`
- [x] `pyproject.toml` — remove `websockets` dependency
- [x] `app/services/conversion_authoring.py` — replace `open_asset_reader` import from episodes with module-level wrapper around `RosReader.open`
- [x] `app/services/__init__.py` — remove episode service exports

**After Phase 2:** 85 tests passing. All episode and visualization code removed.

---

## Phase 3 — Remove Output Actions ✅ COMPLETE

Everything touching the `OutputAction` DB model and the `/actions` sub-routes.

- [x] `app/api/outputs.py` — remove `POST /outputs/{id}/actions` endpoint (`create_output_action_route`)
- [x] `app/api/outputs.py` — remove `GET /outputs/{id}/actions` endpoint (`list_output_actions_route`)
- [x] `app/api/outputs.py` — remove `GET /outputs/actions/{action_id}` endpoint (`get_output_action_route`)
- [x] `app/api/outputs.py` — remove `output_actions_router` and its single alias endpoint *(router kept as empty stub, removed from main)*
- [x] `app/api/outputs.py` — remove `DbSession` dependency and all `session` params from remaining endpoints
- [x] `app/api/outputs.py` — remove `get_latest_output_actions` import and `latest_action` injection
- [x] `app/main.py` — remove `output_actions_router` import and `app.include_router(output_actions_router)`
- [x] Delete `app/services/output_actions.py`
- [x] `app/schemas/outputs.py` — remove `OutputActionCreateRequest`, `OutputActionDetailResponse`, `OutputActionSummaryResponse`
- [x] `app/schemas/outputs.py` — remove `latest_action` field from `OutputArtifactSummaryResponse`
- [x] `app/mappers/workspace.py` — remove `latest_action=None` from `map_output_summary`
- [x] `app/schemas/__init__.py` — remove output action schema exports
- [x] `app/services/__init__.py` — remove output action service exports
- [x] `tests/test_api_outputs.py` — remove `test_output_actions_*` tests

**After Phase 3:** 83 tests passing. `OutputAction` model has no writers. Both DB tables are dead. `app/services/jobs.py` is still dead from Phase 1.

---

## Phase 4 — Remove Backend DB ✅ COMPLETE

Eliminate SQLAlchemy, the session factory, and all DB infrastructure.

- [x] `app/services/dashboard.py` — remove `session: Session` from all 3 functions, remove `_backend_visualization_jobs`, inline `utc_now` from `datetime.now(UTC)`
- [x] `app/api/dashboard.py` — remove `DbSession` dependency from all three route handlers
- [x] Delete `app/services/jobs.py`
- [x] Delete `app/db/models.py`, `app/db/session.py`, `app/db/__init__.py`, `app/db/` directory
- [x] `app/main.py` — remove engine/session factory creation and teardown
- [x] `app/config.py` — remove `database_path` and `database_url` fields
- [x] `app/dependencies.py` — remove `get_db_session`
- [x] `app/services/__init__.py` — remove Job service exports
- [x] `pyproject.toml` — remove `sqlalchemy` dependency
- [x] `tests/conftest.py` — remove `backend_db_path` fixture and `HEPHAES_BACKEND_DB_PATH` env var
- [x] `tests/test_config.py` — remove `database_path` assertions
- [x] `tests/test_api_dashboard_phase1.py` — remove `JobService` visualization job setup
- [x] `tests/test_api_dashboard_phase2.py` — remove `JobService`/`Job` usage, update job count assertions (active_count=0, queued=0, running=0), update `latest_job_update_at` to workspace max
- [x] `tests/test_authoring_contracts.py` — remove `test_backend_database_only_keeps_runtime_tables` (premise eliminated)

**After Phase 4:** 82 tests passing. Backend has zero SQLAlchemy/ORM dependencies. All state lives in hephaes `workspace.db`.

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
