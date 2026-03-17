# Backend Phase 6

## Goal

Wrap the `hephaes` package with conversion APIs so the frontend never calls the conversion library directly.

## Scope

Create conversion flows where:

- the frontend sends asset IDs plus conversion config
- the backend resolves those IDs to file paths
- the backend calls into `hephaes`
- outputs are written to a local output directory
- conversion results are tracked in the database

Suggested output location:

- `backend/data/outputs/`
- or a configurable local `outputs/` directory

## API Surface

Add these routes:

- `POST /conversions`
- `GET /conversions`
- `GET /conversions/{conversion_id}`

Use the `jobs` table from phase 5 as the execution backbone for conversions. Add a dedicated `conversions` table only if you want separate conversion history or domain-specific fields beyond generic job tracking.

Suggested stored fields:

- `id`
- `job_id`
- `status`
- `config_json`
- `output_path`
- `created_at`
- `updated_at`

## Integration with `hephaes`

Examples of logic that should stay in `hephaes`:

- conversion entrypoints
- mapping validation
- output writing logic
- reusable conversion result models

Examples of logic that should stay in the backend:

- request validation
- asset ID resolution
- local output directory management
- job status updates

`POST /conversions` should create a conversion workflow that is traceable through the jobs system, even if the response also exposes a conversion-specific ID.

## Deliverable

By the end of phase 6, you should be able to:

- request a conversion from the frontend
- run conversion through the backend
- store status and output location
- list past conversion runs

## Implementation Plan

### Conversion contract

- Decide the first supported conversion request shape for [POST /conversions](/Users/danielyoo/workspace/hephaes/design/backend-phase6.md), including:
  - source asset IDs
  - conversion type or mode
  - mapping or selection config
  - output naming hints if needed
- Keep the request minimal for the first cut and avoid exposing raw filesystem paths to the frontend.
- Define which parts of the conversion payload are backend-owned versus passed directly into `hephaes`.
- Document any assumptions about single-asset versus multi-asset conversions so the initial API stays predictable.

### Output directory management

- Add backend-owned output directory resolution in [backend/app/config.py](/Users/danielyoo/workspace/hephaes/backend/app/config.py) or a dedicated conversion service helper.
- Default outputs to a local directory such as `backend/data/outputs/`, while allowing the path to be configurable for local development.
- Ensure output directories are created safely before conversion starts.
- Decide how output names are generated so repeated conversions do not silently overwrite earlier results.

### `hephaes` integration wrapper

- Add a dedicated conversion service module, for example [backend/app/services/conversions.py](/Users/danielyoo/workspace/hephaes/backend/app/services/conversions.py), so route handlers never call `hephaes` directly.
- Keep `hephaes` responsible for:
  - conversion entrypoints
  - mapping validation
  - output writing
  - reusable result payloads
- Keep the backend wrapper responsible for:
  - validating asset IDs
  - resolving asset IDs to file paths
  - assembling backend-safe conversion config
  - choosing output locations
  - persisting job and conversion status
- Return clear domain errors when conversion inputs are invalid, assets are missing, or `hephaes` fails.

### Persistence model

- Decide whether phase 6 uses only the phase 5 `jobs` table or adds a dedicated `conversions` table as well.
- If a `conversions` table is added in [backend/app/db/models.py](/Users/danielyoo/workspace/hephaes/backend/app/db/models.py), include fields such as:
  - `id`
  - `job_id`
  - `status`
  - `config_json`
  - `output_path`
  - `created_at`
  - `updated_at`
- Keep `job_id` as the durable link back to the generic job system.
- Decide whether conversion history needs domain-specific fields now or whether generic job metadata is sufficient for the first iteration.

### Job-system integration

- Reuse the phase 5 job service in [backend/app/services/jobs.py](/Users/danielyoo/workspace/hephaes/backend/app/services/jobs.py) for conversion execution.
- Create a `convert` job before conversion starts and move it through:
  - `queued`
  - `running`
  - `succeeded`
  - `failed`
- Persist output location on the job record when conversion succeeds.
- Persist readable failure messages on the job record when conversion fails.
- Keep the conversion service generic enough that later visualization-preparation work can share the same execution pattern.

### Execution model

- Use the same in-process execution strategy chosen in phase 5 unless there is a strong reason to split it.
- Decide whether `POST /conversions` runs synchronously for the first cut or kicks off a background-capable job flow while immediately returning the created job or conversion record.
- If synchronous execution is kept initially, still persist the full job lifecycle so the frontend can rely on durable status.
- Avoid introducing Redis, Celery, or external workers in this phase.

### API schemas

- Add typed request and response schemas for conversions, either in [backend/app/schemas/assets.py](/Users/danielyoo/workspace/hephaes/backend/app/schemas/assets.py) or a dedicated schema module such as [backend/app/schemas/conversions.py](/Users/danielyoo/workspace/hephaes/backend/app/schemas/conversions.py).
- Define the response shape for:
  - `POST /conversions`
  - `GET /conversions`
  - `GET /conversions/{conversion_id}`
- Include enough information for the frontend to render:
  - current status
  - source assets
  - conversion config summary
  - output path
  - linked job ID
- Keep payloads frontend-friendly and avoid leaking internal backend-only fields unless they are genuinely useful.

### Route implementation

- Add a dedicated conversions router, for example [backend/app/api/conversions.py](/Users/danielyoo/workspace/hephaes/backend/app/api/conversions.py).
- Implement `POST /conversions` so it:
  - validates the request
  - resolves asset IDs
  - creates the job and any conversion record
  - triggers conversion execution
  - returns a traceable response
- Implement `GET /conversions` with stable ordering, such as newest first.
- Implement `GET /conversions/{conversion_id}` with clear `404` behavior for missing records.
- Decide whether early filtering by status or source asset belongs in phase 6 or remains a later enhancement.

### Result and download behavior

- Decide whether conversion responses expose only the local output path or also include derived metadata such as file name and size.
- Keep output-path behavior explicit, especially if the frontend will later need download links or preview links.
- Decide whether phase 6 includes any route for serving or downloading outputs, or whether it only records where outputs were written.
- If download-serving is deferred, document that clearly so the frontend does not assume an HTTP file endpoint exists yet.

### Tests

- Add backend tests for successful conversion creation and completion.
- Add tests for invalid asset IDs or invalid conversion config.
- Add tests for failed conversion jobs and persisted error messages.
- Add tests for `GET /conversions` ordering and response shape.
- Add tests for `GET /conversions/{conversion_id}` success and `404` behavior.
- Add tests confirming conversion flows create linked `convert` jobs in the phase 5 jobs system.
- Add tests ensuring output paths are persisted and do not regress if conversion execution becomes asynchronous later.

### Local verification

- Run the backend locally and trigger a real conversion through the API.
- Confirm the backend resolves asset IDs to paths correctly and writes outputs into the configured local output directory.
- Confirm a `convert` job is created and reaches the expected final status.
- Confirm successful conversion runs expose a stable output path through the conversion and job APIs.
- Confirm failed conversions surface readable errors without leaving ambiguous partial state in the database.
