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
