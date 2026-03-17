# Backend Phase 7

## Goal

Improve local file ingestion so the app has a smoother workflow for bringing files into the system.

## Ingestion Options

### Option A: Register file or folder paths

The frontend sends:

- a file path
- or a directory path for scanning

The backend scans for supported file types such as `.bag` and `.mcap`.

Pros:

- fast for local power users
- simple backend logic

Cons:

- browser apps do not always handle arbitrary local paths cleanly
- more environment-dependent UX

### Option B: Upload files through the frontend

The frontend uploads files to the backend, and the backend stores them in a managed directory such as:

- `backend/data/raw/`

Pros:

- more consistent web-app behavior
- easier to reason about ownership and file lifecycle

Cons:

- requires file copy and storage management
- larger files may take time to upload even locally

## Recommendation

Phase 1 starts with path registration because it is the fastest way to get the app working. Once the rest of the backend is in place, upload is usually the more stable long-term default because it gives the backend a predictable managed location. Path registration and folder scanning can remain available for advanced local workflows.

## API Surface

Potential routes:

- `POST /assets/upload`
- `POST /assets/register`
- `POST /assets/scan-directory`
- `GET /assets/{asset_id}/episodes`

## Asset Detail Expansion

At this point, `GET /assets/{asset_id}` should be an aggregated endpoint that can return:

- base asset info
- extracted metadata
- topic inventory and visualization summary
- episode list or default episode summary
- tags
- related jobs
- prior conversions

That allows the frontend detail page to load from one main request instead of stitching together several calls.

## Deliverable

By the end of phase 7, you should have:

- a stable local ingestion story
- a managed path for uploaded files
- optional directory scanning for advanced users
- a richer asset detail endpoint for the frontend
- an episode discovery surface that the frontend can use to launch visualization

## Tasks

### Ingestion contract

- Decide the first-cut ingestion modes that phase 7 will support together:
  - managed upload into a backend-owned raw-data directory
  - directory scanning for advanced local workflows
  - existing direct registration for power users
- Keep the public API explicit about which routes create backend-owned copies versus which routes only register existing local files.
- Define how duplicate detection works across uploaded assets and path-registered assets so the registry stays predictable.
- Document the supported file types for upload and scan flows in the route schemas and service layer.

### Managed upload storage

- Add backend-owned raw-file storage configuration in [backend/app/config.py](/Users/danielyoo/workspace/hephaes/backend/app/config.py), for example under `backend/data/raw/`.
- Ensure uploaded files are written into unique managed directories or filenames so repeated uploads do not silently overwrite earlier data.
- Decide whether uploaded files preserve the original filename, and if so how collisions are handled.
- Keep path ownership clear so later cleanup, reindexing, and conversion work can rely on stable managed file locations.

### Upload service layer

- Add upload helpers in [backend/app/services/assets.py](/Users/danielyoo/workspace/hephaes/backend/app/services/assets.py) or a dedicated ingestion service module.
- Validate uploaded file names, file extensions, and empty uploads before writing anything to disk.
- Write uploaded files safely to the managed raw directory and then register them through the existing asset-registration flow.
- Return clear domain errors for unsupported file types, duplicate uploads, and storage failures.

### Directory scanning

- Add a directory-scan helper that accepts a local directory path and finds supported asset files such as `.bag` and `.mcap`.
- Decide whether scanning is recursive in the first cut and document that behavior clearly.
- Reuse the existing registration logic for each discovered file so metadata such as size and type stays consistent with other ingestion paths.
- Return a structured scan result that distinguishes:
  - newly registered files
  - duplicates
  - invalid or unreadable paths

### Episode discovery

- Add an episode-discovery service that can derive episode summaries for a given asset from indexed metadata or `hephaes`-level helpers.
- Implement [GET /assets/{asset_id}/episodes](/Users/danielyoo/workspace/hephaes/design/backend-phase7.md) with a stable response shape for:
  - episode IDs
  - labels
  - start and end timing
  - duration
  - any first-cut visualization readiness hints
- Keep the first cut minimal, but make sure the response is sufficient for the frontend visualization entry flow planned in later phases.
- Decide how unindexed assets behave and return a clear error or empty-state response instead of ambiguous partial data.

### Aggregated asset detail

- Expand [GET /assets/{asset_id}](/Users/danielyoo/workspace/hephaes/backend/app/api/assets.py) so it can return one richer detail payload instead of forcing the frontend to stitch together multiple calls.
- Extend the asset detail schema in [backend/app/schemas/assets.py](/Users/danielyoo/workspace/hephaes/backend/app/schemas/assets.py) to include:
  - base asset info
  - indexed metadata
  - tags
  - episode list or episode summary
  - related jobs
  - prior conversions
- Keep the response grouped and frontend-friendly so later UI work can load one main detail request without extra joins in the browser.
- Avoid overfetching raw internal fields that the frontend does not need yet.

### Jobs and conversions integration

- Add service queries that associate assets with related job history and prior conversions.
- Decide the first-cut ordering for related jobs and conversions, such as newest first with a small bounded list.
- Keep the aggregated detail query efficient enough for local use even when an asset has multiple indexing and conversion runs.
- Reuse existing job and conversion schemas where possible instead of inventing duplicate response models.

### API routes

- Add `POST /assets/upload`.
- Add `POST /assets/scan-directory`.
- Add `GET /assets/{asset_id}/episodes`.
- Update `GET /assets/{asset_id}` to return the richer aggregated shape.
- Keep error handling consistent with the earlier backend phases:
  - `404` for missing assets
  - `400` or `422` for invalid paths or invalid payloads
  - clear duplicate and unsupported-file responses

### Tests

- Add backend tests for successful file upload and registration.
- Add tests for upload rejection cases such as unsupported file type, empty upload, and duplicate file registration.
- Add tests for directory scanning success, duplicate handling, and invalid directory paths.
- Add tests for `GET /assets/{asset_id}/episodes` on indexed assets plus the expected behavior for unindexed or missing assets.
- Add tests for the richer `GET /assets/{asset_id}` response shape, including tags, related jobs, conversions, and episode data.
- Add tests that confirm upload-backed assets still work with existing indexing and conversion flows.

### Local verification

- Run the backend locally and verify that a file uploaded through the new API is stored in the managed raw-data directory and appears in the asset registry.
- Verify that directory scanning finds supported files and reports duplicates cleanly.
- Verify that indexed assets expose episode discovery data through the new episodes route.
- Verify that the aggregated asset detail route returns enough information for the frontend to render a detail page without extra round trips.
- Verify that uploaded assets can still be indexed and converted end to end after ingestion.
