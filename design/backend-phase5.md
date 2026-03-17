# Backend Phase 5

## Goal

Introduce job tracking so indexing and conversion operations have durable status, error reporting, and frontend visibility.

## Scope

Create a `jobs` table with fields such as:

- `id`
- `type`
- `status`
- `target_asset_ids_json`
- `config_json`
- `output_path`
- `error_message`
- `created_at`
- `updated_at`

Recommended job types:

- `index`
- `convert`
- `prepare_visualization`

Recommended job statuses:

- `queued`
- `running`
- `succeeded`
- `failed`

## Execution Model

Do not add Redis or Celery yet.

Start with one of these:

- FastAPI background tasks
- a small in-process job manager
- a thread pool executor

The important part in this phase is the persisted job record, not distributed execution.

This phase should become the execution backbone for indexing and conversion work. Routes can trigger work through the job system even if execution still happens in-process.

## API Surface

Add these routes:

- `GET /jobs`
- `GET /jobs/{job_id}`

Update indexing and conversion flows so they create and update `jobs` records.

## Frontend Value

This phase powers:

- a jobs page
- progress and status indicators
- retry and failure messaging later
- preview-generation or cache-warming flows for visualization later

## Deliverable

By the end of phase 5, you should be able to:

- create a job record when indexing or conversion starts
- track queued, running, success, and failure states
- show job status in the frontend without guessing from asset rows alone
- keep the job system generic enough for future visualization-preparation work

## Tasks

### Database schema

- Add a `jobs` table in [backend/app/db/models.py](/Users/danielyoo/workspace/hephaes/backend/app/db/models.py) with stable IDs, timestamps, job type, job status, target asset references, config payload, output path, and error message fields.
- Define explicit allowed values for job types such as:
  - `index`
  - `convert`
  - `prepare_visualization`
- Define explicit allowed values for job statuses such as:
  - `queued`
  - `running`
  - `succeeded`
  - `failed`
- Decide whether `target_asset_ids_json` stays as JSON for phase 5 or whether a future join table is likely, and document that tradeoff in the model comments or phase notes.
- Add any helpful indexes for common job queries, for example by `created_at`, `status`, or `type`.

### Job service layer

- Add a dedicated job service module, for example in [backend/app/services/jobs.py](/Users/danielyoo/workspace/hephaes/backend/app/services/jobs.py), so route handlers and indexing code do not mutate job rows directly.
- Add service helpers for:
  - creating a queued job
  - marking a job as running
  - marking a job as succeeded
  - marking a job as failed
  - listing jobs
  - fetching a single job
- Keep job state transitions centralized so queued, running, success, and failure behavior stays consistent across indexing and later conversion flows.
- Decide how much execution metadata phase 5 stores now, such as started and finished timestamps, and keep that consistent with the service API.

### Execution model

- Pick the in-process execution strategy for phase 5:
  - FastAPI background tasks
  - a small in-process job manager
  - a thread pool executor
- Keep the execution layer lightweight and local-first; do not introduce Redis, Celery, or external workers in this phase.
- Make sure execution entrypoints always create the job record before work starts and always finalize the job record on success or failure.
- Ensure failures are persisted even if the underlying indexing or conversion service raises an exception.
- Keep the design generic enough that future visualization-preparation jobs can reuse the same execution path.

### API schemas

- Extend [backend/app/schemas/assets.py](/Users/danielyoo/workspace/hephaes/backend/app/schemas/assets.py) or add a dedicated jobs schema module with typed request and response models for job records.
- Add a reusable job response shape that includes:
  - `id`
  - `type`
  - `status`
  - `target_asset_ids_json`
  - `config_json`
  - `output_path`
  - `error_message`
  - `created_at`
  - `updated_at`
- Decide whether phase 5 also includes lightweight execution timestamps or progress fields, and document the response contract clearly.
- Keep job payloads frontend-friendly so a jobs page can render them without backend-specific interpretation.

### Route implementation

- Add a jobs router or extend the existing API surface with:
  - `GET /jobs`
  - `GET /jobs/{job_id}`
- Implement stable job ordering, such as newest created first.
- Decide whether `GET /jobs` supports early filtering by status or type in phase 5 or stays as a plain list for the first cut.
- Return clear `404` responses for missing jobs and keep route handlers thin by delegating to the service layer.

### Indexing integration

- Update indexing flows so index operations create and update `jobs` records instead of only mutating asset rows.
- Decide whether `POST /assets/{asset_id}/index` returns:
  - the created job
  - the updated asset detail plus job info
  - or keeps the current response and relies on `GET /jobs`
- Keep asset indexing status and job status aligned so the two sources of truth do not drift.
- Ensure indexing failures populate both the asset failure fields and the corresponding job error fields.
- Update bulk indexing flows such as `POST /assets/reindex-all` so they create jobs in a predictable way, whether that means one job per asset or one parent job representing the batch.

### Conversion and visualization-prep hooks

- Define the generic job service interface so future conversion work in later phases can register `convert` jobs without reshaping the table.
- Reserve enough config structure in `config_json` for future conversion and visualization-preparation inputs.
- Decide whether phase 5 stubs out unused job types now or simply documents them as supported future values.
- Avoid baking indexing-only assumptions into job naming, payload shape, or route behavior.

### Response integration

- Decide whether asset detail responses or list rows should expose the latest related job in phase 5, or whether the frontend will initially read jobs separately.
- If asset responses include job info, keep that assembly centralized so metadata, tags, and job state stay consistent across routes.
- If asset responses do not include job info yet, document clearly how the frontend should correlate assets with jobs during this phase.

### Tests

- Add backend tests for job creation and retrieval.
- Add tests for job state transitions from queued to running to succeeded.
- Add tests for failed jobs and persisted error messages.
- Add tests confirming indexing routes create job records.
- Add tests for missing-job `404` behavior.
- Add tests for stable job ordering in `GET /jobs`.
- Add tests for any chosen batch-indexing job behavior so the API contract is explicit before the frontend depends on it.

### Local verification

- Run the backend locally and trigger indexing through the real API.
- Confirm a job record appears when work begins and updates as the work progresses.
- Confirm failed indexing produces a failed job with a readable error message.
- Confirm `GET /jobs` and `GET /jobs/{job_id}` are enough for a frontend jobs page to render meaningful status.
- Confirm the job system still works if indexing finishes quickly and does not only behave correctly in long-running cases.
