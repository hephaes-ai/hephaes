# Backend Phase 9

## Goal

Prepare and deliver official Rerun viewer sources so the frontend can embed the open-source `rerun-io/rerun` web viewer without translating raw bag data in the browser.

## Depends On

- [backend-phase5.md](/Users/danielyoo/workspace/hephaes/design/backend-phase5.md) for durable jobs
- [backend-phase6.md](/Users/danielyoo/workspace/hephaes/design/backend-phase6.md) for managed outputs
- [backend-phase8.md](/Users/danielyoo/workspace/hephaes/design/backend-phase8.md) for episode, stream, timeline, and synchronized playback metadata

## Scope

Add a backend-managed Rerun delivery layer where the backend can:

- prepare an episode-level Rerun recording or another official viewer-compatible source
- cache or reuse prepared viewer artifacts
- expose a frontend-friendly viewer-source manifest
- surface job state while viewer artifacts are being prepared
- keep viewer-version compatibility explicit

The main rendering path for the official viewer should use a Rerun-native source such as a hosted `.rrd` file or another official source type supported by the viewer. The frontend should not be expected to reconstruct the main visual scene from generic JSON samples.

## API Surface

Add or complete routes such as:

- `POST /assets/{asset_id}/episodes/{episode_id}/prepare-visualization`
- `GET /assets/{asset_id}/episodes/{episode_id}/viewer-source`

Suggested behavior:

- `POST /assets/{asset_id}/episodes/{episode_id}/prepare-visualization` creates or refreshes a durable `prepare_visualization` job for the selected episode
- `GET /assets/{asset_id}/episodes/{episode_id}/viewer-source` returns the current viewer-source manifest, including whether a cached recording already exists or is still being prepared

Suggested manifest fields:

- `episode_id`
- `status`
- `source_kind`
- `source_url`
- `job_id`
- `artifact_path`
- `viewer_version`
- `recording_version`
- `updated_at`

Suggested source kinds:

- `rrd_url`
- `grpc_url`

## Payload Guidance

The viewer-source manifest should be lightweight and stable enough for the frontend to:

- decide whether the viewer is ready
- show a prepare-in-progress state
- pass a compatible URL into the official Rerun viewer component
- detect obvious version mismatches before the user sees a broken viewer shell

Keep artifact-serving details backend-owned. The frontend should not need to know where cached recordings live on disk beyond the URL or manifest fields required to load them.

## Versioning Guidance

The backend should make version compatibility explicit.

At minimum:

- pin the backend Rerun recording generation to a known version
- expose enough metadata for the frontend to keep its viewer package aligned
- avoid silently serving recordings from an incompatible format version

## Deliverable

By the end of phase 9, you should be able to:

- request visualization preparation for an indexed episode
- inspect the durable job state for visualization preparation
- fetch a stable viewer-source manifest for that episode
- embed the official Rerun viewer against a backend-provided source without the browser parsing raw bag files directly

## Tasks

### Rerun integration contract

- Decide the first official viewer source type the backend will support:
  - hosted `.rrd` files
  - or another official source type such as a compatible gRPC endpoint
- Keep the first cut narrow and predictable instead of supporting every possible viewer source mode.
- Define how the backend maps one indexed episode into one viewer source artifact.
- Document what the frontend can assume about viewer-source lifecycle, reuse, and invalidation.

### Recording generation service

- Add a dedicated service module, for example [backend/app/services/visualization.py](/Users/danielyoo/workspace/hephaes/backend/app/services/visualization.py), that owns official Rerun recording generation and lookup.
- Keep the service responsible for:
  - resolving assets and episodes
  - building or refreshing viewer artifacts
  - choosing output locations
  - returning stable viewer-source manifests
  - updating durable job state
- Reuse the phase 8 episode and stream metadata instead of rediscovering playback context from scratch on every request.

### Artifact storage

- Choose a managed storage location under backend-owned outputs for prepared viewer artifacts.
- Ensure repeated preparation runs do not silently overwrite unrelated artifacts.
- Decide whether artifacts are keyed by:
  - episode ID
  - asset-plus-episode revision
  - or a cache key that includes backend versioning inputs
- Keep artifact cleanup and reuse predictable for local development.

### Jobs integration

- Reuse the phase 5 `prepare_visualization` job type for viewer-artifact preparation.
- Add helpers that create, refresh, and inspect visualization-prep jobs.
- Make the manifest route reflect whether a usable artifact already exists, is being prepared, or failed to prepare.
- Decide whether `POST /assets/{asset_id}/episodes/{episode_id}/prepare-visualization` always creates a fresh job or reuses an in-flight or cached result when appropriate.

### Viewer-source manifest route

- Implement `GET /assets/{asset_id}/episodes/{episode_id}/viewer-source`.
- Return a manifest that includes:
  - source readiness status
  - source kind
  - source URL when ready
  - linked job ID when preparing or failed
  - version metadata
  - artifact timestamps
- Keep the manifest easy for the frontend to poll without downloading the artifact itself.

### Artifact serving

- Decide how prepared `.rrd` artifacts or equivalent viewer sources are served locally.
- If the backend serves files directly, keep the route stable and cache-aware.
- If a separate artifact-serving layer is introduced later, keep the manifest contract stable so the frontend does not change.
- Avoid exposing arbitrary local file paths directly as the primary integration contract.

### Version compatibility

- Record the backend-side Rerun generation version used for each prepared artifact.
- Expose viewer compatibility metadata in the manifest so the frontend can keep its official viewer package aligned.
- Decide how incompatible cached artifacts are invalidated or regenerated after a version bump.
- Add clear failure messaging for incompatible or stale visualization artifacts.

### API schemas

- Add dedicated visualization-prep and viewer-source schemas in [backend/app/schemas/episodes.py](/Users/danielyoo/workspace/hephaes/backend/app/schemas/episodes.py) or a dedicated visualization schema module.
- Keep the manifest explicit about readiness, source kind, URLs, and versioning fields.
- Reuse job response models where possible instead of inventing duplicate status structures.

### Tests

- Add backend tests for successful visualization-prep job creation.
- Add tests for viewer-source manifest behavior when:
  - no artifact exists yet
  - an artifact is being prepared
  - an artifact is ready
  - preparation failed
- Add tests for stable artifact reuse when the same episode is requested repeatedly.
- Add tests for version metadata and incompatible-artifact handling if phase 9 includes explicit validation.
- Add tests for missing-asset and missing-episode behavior across the new routes.

### Local verification

- Run the backend locally and prepare visualization for a real indexed episode.
- Confirm a durable `prepare_visualization` job is created and transitions to the expected status.
- Confirm the viewer-source manifest exposes a stable backend-owned source URL when ready.
- Confirm the produced source loads in the official Rerun viewer with the intended frontend package version.
- Confirm cached artifacts are reused or regenerated in the expected cases.

---

## Implementation Tasks

### 1. Add visualization schemas

Create [backend/app/schemas/visualization.py](backend/app/schemas/visualization.py) with Pydantic models following the existing `ConfigDict(extra="forbid")` pattern.

- [ ] Add `SourceKind = Literal["rrd_url", "grpc_url"]` type alias
- [ ] Add `ViewerSourceStatus = Literal["none", "preparing", "ready", "failed"]` type alias
- [ ] Add `PrepareVisualizationResponse` schema wrapping a `JobResponse` (reuse from [backend/app/schemas/jobs.py](backend/app/schemas/jobs.py))
- [ ] Add `ViewerSourceResponse` schema with fields: `episode_id`, `status` (ViewerSourceStatus), `source_kind` (optional SourceKind), `source_url` (optional str), `job_id` (optional str), `artifact_path` (optional str), `viewer_version` (optional str), `recording_version` (optional str), `updated_at` (optional datetime)
- [ ] Add UTC datetime normalization validators consistent with [backend/app/schemas/episodes.py](backend/app/schemas/episodes.py)

### 2. Add visualization service

Create [backend/app/services/visualization.py](backend/app/services/visualization.py) following the class-based pattern from `ConversionService` and `JobService`.

- [ ] Add `VisualizationService` class that takes a `Session` in its constructor
- [ ] Add `prepare_visualization(asset_id: str, episode_id: str) -> Job` method that:
  - Validates the asset exists via `get_asset_or_raise()` from [backend/app/services/assets.py](backend/app/services/assets.py)
  - Validates the episode exists via `get_episode_detail()` from [backend/app/services/episodes.py](backend/app/services/episodes.py)
  - Checks for an existing in-flight or succeeded `prepare_visualization` job for the same episode (query `Job` table by type and target asset)
  - If a cached artifact already exists and the job succeeded, returns the existing job (skip re-preparation)
  - Otherwise creates a new job via `JobService.create_job(type="prepare_visualization", ...)`
  - Marks the job running, invokes the recording generation logic, marks succeeded or failed
- [ ] Add `get_viewer_source(asset_id: str, episode_id: str) -> ViewerSourceManifest` method that:
  - Looks up the most recent `prepare_visualization` job for the episode
  - If no job exists, returns a manifest with `status="none"`
  - If job is queued/running, returns `status="preparing"` with the `job_id`
  - If job succeeded, returns `status="ready"` with `source_kind`, `source_url`, version metadata, and `artifact_path`
  - If job failed, returns `status="failed"` with `job_id` and `error_message`
- [ ] Add `_generate_rrd(asset_id: str, episode_id: str, output_path: Path) -> Path` private method that:
  - Opens the asset file via `RosReader` (reuse pattern from [backend/app/services/episodes.py](backend/app/services/episodes.py))
  - Reads episode streams and writes a `.rrd` recording using the `rerun` Python SDK
  - Returns the output path of the generated `.rrd` file
- [ ] Add exception classes: `VisualizationError`, `VisualizationNotFoundError`, `VisualizationGenerationError`
- [ ] Add a `_artifact_output_dir(asset_id: str, episode_id: str) -> Path` helper that resolves the output location under `settings.outputs_dir / "visualizations" / asset_id / episode_id`
- [ ] Add a `_find_cached_artifact(asset_id: str, episode_id: str) -> Path | None` helper that checks whether a valid `.rrd` file already exists at the expected output path

### 3. Add visualization API routes

Create [backend/app/api/visualization.py](backend/app/api/visualization.py) following the router pattern from [backend/app/api/episodes.py](backend/app/api/episodes.py).

- [ ] Create router with `prefix="/assets/{asset_id}/episodes/{episode_id}"` and `tags=["visualization"]`
- [ ] Add `POST /prepare-visualization` route that:
  - Accepts `asset_id` and `episode_id` path parameters
  - Calls `VisualizationService.prepare_visualization()`
  - Returns `PrepareVisualizationResponse` (wrapping the job)
  - Maps `VisualizationError` → 422, `EpisodeNotFoundError` → 404, `AssetNotFoundError` → 404
- [ ] Add `GET /viewer-source` route that:
  - Accepts `asset_id` and `episode_id` path parameters
  - Calls `VisualizationService.get_viewer_source()`
  - Returns `ViewerSourceResponse`
  - Maps `AssetNotFoundError` → 404, `EpisodeNotFoundError` → 404

### 4. Register router and add artifact serving

Update [backend/app/main.py](backend/app/main.py) and configure static file serving for generated artifacts.

- [ ] Import and register the visualization router via `app.include_router(visualization_router)`
- [ ] Add a `GET /visualizations/{asset_id}/{episode_id}/{filename}` static file route or mount a `StaticFiles` handler under `/visualizations` pointing at `settings.outputs_dir / "visualizations"`
- [ ] Ensure the `source_url` returned in the viewer-source manifest maps to the serving route (e.g., `/visualizations/{asset_id}/{episode_id}/recording.rrd`)

### 5. Pin Rerun version and add version metadata

Update [backend/app/config.py](backend/app/config.py) and the visualization service to make version compatibility explicit.

- [ ] Add `RERUN_SDK_VERSION` constant in config (pinned to the installed `rerun-sdk` package version)
- [ ] Add `RERUN_RECORDING_VERSION` constant (the `.rrd` format version produced by the pinned SDK)
- [ ] Populate `viewer_version` and `recording_version` fields in the viewer-source manifest from these constants
- [ ] In `_generate_rrd`, tag the recording with the SDK version used for generation
- [ ] In `get_viewer_source`, compare the cached artifact's recording version against the current `RERUN_RECORDING_VERSION` and mark stale artifacts as needing regeneration

### 6. Add rerun SDK dependency

Update project dependency configuration.

- [ ] Add `rerun-sdk` to the backend's dependencies (in `pyproject.toml` or equivalent)
- [ ] Verify import works: `import rerun as rr`
- [ ] Document the pinned version in a comment so future bumps are intentional

### 7. Add tests

Create [backend/tests/test_api_visualization.py](backend/tests/test_api_visualization.py) following the pattern from [backend/tests/test_api_episodes.py](backend/tests/test_api_episodes.py).

- [ ] Add test for `POST /prepare-visualization` with a valid indexed episode → 200, returns job with `type="prepare_visualization"`
- [ ] Add test for `POST /prepare-visualization` with a nonexistent asset → 404
- [ ] Add test for `POST /prepare-visualization` with a nonexistent episode → 404
- [ ] Add test for `GET /viewer-source` when no preparation has been requested → returns `status="none"`
- [ ] Add test for `GET /viewer-source` after successful preparation → returns `status="ready"`, `source_kind="rrd_url"`, and a valid `source_url`
- [ ] Add test for `GET /viewer-source` reflecting a failed preparation → returns `status="failed"` with `job_id`
- [ ] Add test for repeated `POST /prepare-visualization` on the same episode → reuses cached artifact / existing job instead of creating duplicates
- [ ] Add test for `GET /viewer-source` includes `viewer_version` and `recording_version` when ready
- [ ] Add test that the `source_url` from the manifest is actually servable (GET returns 200 with content)

### 8. Wire up job lookup helpers

Extend [backend/app/services/jobs.py](backend/app/services/jobs.py) to support querying jobs by type and target.

- [ ] Add `find_latest_job_for_target(session, job_type: str, target_asset_id: str) -> Job | None` helper that queries the most recent job matching the type and target asset, ordered by `created_at` descending
- [ ] Use this helper in `VisualizationService` to check for existing in-flight or cached jobs before creating new ones
- [ ] Add `find_jobs_for_episode(session, job_type: str, episode_id: str) -> list[Job]` if job-episode association needs to be tracked (consider adding `episode_id` to `Job.config_json` as the linking key)
