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

## Deliverable

By the end of phase 5, you should be able to:

- create a job record when indexing or conversion starts
- track queued, running, success, and failure states
- show job status in the frontend without guessing from asset rows alone
