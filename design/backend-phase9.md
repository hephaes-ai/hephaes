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
