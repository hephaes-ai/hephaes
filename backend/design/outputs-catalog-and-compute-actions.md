# Outputs Catalog And Compute Actions

## Goal

Add a first-class backend surface for browsing conversion outputs and launching output-scoped compute actions, starting with optional VLM tagging backed by an external compute provider such as `hephaes-ml`.

This should make conversion artifacts discoverable outside of individual asset and job pages, while keeping the design compatible with the backend's current local-first, SQLite-plus-filesystem architecture.

## Current Gaps

Today the backend has enough state to show conversion results in a few narrow places, but not enough to support an outputs workspace.

- `conversions` stores run-level metadata, not first-class output artifacts
- `output_files_json` is useful for job detail, but weak for search, filtering, and action targeting
- there is no backend route for listing outputs across all conversions
- there is no stable output ID that a frontend page can navigate to
- there is no output-scoped compute action model yet
- there is no capability model for optional or premium compute providers
- there is no migration layer, so changes to existing constrained tables should be minimized early

## Recommended Design Principles

- Treat conversion outputs as first-class artifacts, not as incidental strings on a conversion row.
- Keep `conversions` as the parent workflow record for how an output was created.
- Prefer additive tables over modifying existing constrained tables, because `create_all()` does not migrate existing SQLite schemas.
- Let this backend own output discovery, validation, and durable action state even when action execution is delegated elsewhere.
- Keep execution inline at first if needed, but persist durable action state so the API contract survives a future worker/queue migration.
- Keep the base backend installable without premium compute packages; optional actions should degrade cleanly when no provider is configured.
- Maintain one-way dependency flow: premium tooling such as `hephaes-ml` may depend on `hephaes`, but the core `hephaes` package and baseline backend should not depend on `hephaes-ml`.
- Scope phase 1 to conversion outputs only, but use generic naming so replay artifacts or other derived datasets can fit later.

## Proposed Domain Model

### Keep `conversions` as the workflow parent

The existing `conversions` row should remain the durable record for:

- source asset IDs
- conversion config
- workflow status
- output directory
- backward-compatible `output_files_json`

That avoids a disruptive refactor and keeps current routes working.

### Add `output_artifacts`

Create a new table that registers each emitted file from a conversion.

Suggested fields:

- `id`
- `conversion_id`
- `job_id`
- `source_asset_ids_json`
- `relative_path`
- `file_name`
- `format`
- `role`
- `media_type`
- `size_bytes`
- `availability_status`
- `metadata_json`
- `created_at`
- `updated_at`

Suggested semantics:

- one row per emitted file, including manifests and sidecars when useful
- `role` distinguishes primary dataset files from manifests or helper files
- `availability_status` is a small backend-owned value such as `ready | missing | invalid`
- `metadata_json` stores lightweight inspectable information such as schema fields, row counts, manifest snippets, or image-bearing columns

This gives the frontend stable output IDs from day one.

### Add `output_actions`

Create a second additive table for output-scoped compute actions.

Suggested fields:

- `id`
- `output_artifact_id`
- `action_type`
- `provider_key`
- `status`
- `config_json`
- `result_json`
- `output_path`
- `error_message`
- `created_at`
- `updated_at`
- `started_at`
- `finished_at`

Recommended status vocabulary:

- `queued`
- `running`
- `succeeded`
- `failed`

This intentionally mirrors the existing workflow language without forcing an early `jobs` table migration.

### Optional compute provider boundary

The backend should own the outputs catalog and action records, but not assume that every action implementation lives inside this repo.

Recommended responsibility split:

- this backend validates the target output, persists `output_actions`, tracks status, and stores result artifacts under backend-owned directories
- an optional provider executes the actual compute for action types such as `vlm_tagging`
- provider absence is a first-class state, not an installation error that breaks unrelated backend features

Recommended phase-2 rule:

- `vlm_tagging` should be modelled as an action type that requires a configured provider, not as a guaranteed built-in capability

Recommended initial provider boundary:

- a small runner interface inside the backend
- an adapter that shells out to a configured `hephaes-ml` CLI or entrypoint in a separate environment

This keeps the premium package separate, avoids a hard runtime import dependency inside the monorepo backend, and still lets the frontend talk to one stable backend API.

### Why not extend `jobs` first

The existing `jobs` table has SQLite check constraints on `type` and an asset-centric target model. Because the app currently relies on `Base.metadata.create_all()` rather than migrations, changing that schema safely for existing local databases is higher risk than adding new tables.

Recommended approach:

- keep phase 1 and phase 2 additive
- let `output_actions` own durable action state at first
- revisit `jobs` unification only after adding a real migration path

## Filesystem Layout

Keep current conversion outputs where they are:

- `data/outputs/conversions/<conversion_id>/...`

Add a dedicated area for output-action results:

- `data/outputs/actions/<action_id>/...`

Recommended ownership rules:

- `output_artifacts.relative_path` is always relative to the linked conversion output directory
- `output_actions.output_path` points at the action result directory
- `result_json` stores compact summaries, while larger artifacts live on disk

## Backend Service And API Shape

### New modules

- `app/services/outputs.py`
- `app/services/output_actions.py`
- `app/services/output_action_providers.py`
- `app/api/outputs.py`
- `app/schemas/outputs.py`

### Read APIs

Recommended initial routes:

- `GET /outputs`
- `GET /outputs/{output_id}`
- `GET /outputs/{output_id}/content`

Recommended `GET /outputs` filters:

- `search`
- `format`
- `role`
- `asset_id`
- `conversion_id`
- `availability`
- `limit`
- `offset`

Recommended response fields for list/detail:

- stable output ID
- conversion ID and job ID
- source asset IDs
- file name and relative path
- format and media type
- size and availability status
- created and updated timestamps
- artifact metadata summary
- latest action summary when present
- available action types and availability reasons when useful
- backend-generated `content_url`

### Compute action APIs

Recommended phase-2 routes:

- `POST /outputs/{output_id}/actions`
- `GET /outputs/{output_id}/actions`
- `GET /output-actions/{action_id}`

Recommended initial action payload shape:

- `action_type`
- optional `provider_key`
- `config`

For `vlm_tagging`, likely config fields are:

- target field or stream key
- prompt template
- max sample count
- overwrite behavior
- optional output format details

Expected action-creation behavior:

- reject unsupported action types for the given output format with a validation error
- reject provider-backed action types when no matching provider is configured with a clear capability error
- persist the chosen `provider_key` on the action row when execution starts

## Metadata Capture Strategy

### At conversion completion

When a conversion succeeds:

1. read `output_files_json`
2. register or upsert `output_artifacts`
3. capture filesystem stats
4. derive basic format and role
5. enrich `metadata_json` from the manifest when available
6. run light format-specific inspection when cheap

### Backfill existing conversions

Because there are already conversions in local databases, phase 1 should include a backfill path.

Recommended options:

- lazy backfill on first `GET /outputs`
- eager backfill on app startup

The lower-risk option is lazy backfill inside the outputs service, because it avoids adding more startup work and naturally handles older databases.

### Format-specific inspection

Keep inspection lightweight in phase 1.

- Parquet: schema fields, row-group count, size, manifest summary
- TFRecord: manifest summary first, deeper inspection later
- JSON sidecars: parse small files for summary metadata

Do not block catalog creation on expensive preview extraction.

## Content Serving

Avoid exposing raw absolute filesystem paths as frontend URLs.

Recommended pattern:

- `GET /outputs/{output_id}/content` validates the artifact record
- the route streams the file or redirects to a backend-controlled internal path
- list/detail responses return `content_url`, not a guessed path

The UI can still display the local absolute path for copy-and-paste workflows, but downloads and previews should go through a backend-owned route.

## Testing Expectations

Add API tests for:

- listing outputs after successful conversions
- ordering and filtering outputs
- output detail lookups
- missing output file detection
- lazy backfill of pre-existing conversions
- action creation and status transitions
- VLM tagging payload validation
- provider-unavailable handling for optional premium actions
- provider-runner success and failure mapping into durable action state

## Phased Approach

### Phase 1: Outputs Catalog Foundation

Backend work:

- add `output_artifacts` table and schemas
- register artifacts when conversions succeed
- implement `GET /outputs` and `GET /outputs/{output_id}`
- add backend-owned content access via `GET /outputs/{output_id}/content`
- implement lazy backfill for older conversions
- keep `conversions.output_files_json` as compatibility data

Exit criteria:

- every successful conversion can be discovered from one outputs API
- outputs have stable IDs
- the frontend can list, filter, and open output artifacts without scraping conversion rows

### Phase 2: First Compute Action With Durable State

Backend work:

- add `output_actions` table and schemas
- implement action creation and detail routes
- add an output-action runner interface plus provider detection
- add a local external-runner path for `vlm_tagging`
- persist result artifacts under `data/outputs/actions/<action_id>/`
- expose latest action summary on output detail and optionally on list rows

Exit criteria:

- a user can start a VLM-tagging run against a single output
- the backend reports a clear unavailable state when no premium provider is configured
- action status survives refreshes
- results can be revisited later from the same output

### Phase 3: Preview, Batch Operations, And Hardening

Backend work:

- add richer preview endpoints for Parquet and TFRecord artifacts
- support batched action creation across multiple outputs
- add searchable metadata fields for image-bearing outputs and schema fields
- introduce migration tooling before altering existing constrained tables such as `jobs`

Exit criteria:

- outputs page can support richer inspection without downloading raw files manually
- compute actions scale beyond one-off single-output runs
- schema evolution is no longer blocked on `create_all()` limitations
