# Conversion Authoring And Reusable Configs

## Purpose

This document tracks backend changes that will be needed to support the new converter authoring model.

This is a planning note only. It does not imply that backend implementation should start yet.

The target product flow is:

- inspect an asset or MCAP
- draft a conversion spec from sampled payloads
- preview the draft
- save a reusable config
- edit and reuse that config later
- submit conversion runs through the saved or edited config

The backend should make that possible without reimplementing converter logic that belongs in `hephaes`.

## Ownership Boundary

### `hephaes` should own

- inspection and inference logic
- draft-spec generation
- preview and validation logic
- config serialization, versioning, and migration
- capability metadata for supported row strategies, feature source kinds, transforms, dtypes, and preview limits

### Backend should own

- stable API contracts
- persistence for saved reusable configs, starter templates, and draft revisions
- resource IDs and history
- preview and conversion execution orchestration
- mapping frontend actions onto `hephaes` library entrypoints

The backend should delegate semantic logic to `hephaes` instead of rebuilding it in service code.

## Why The Backend Needs New Surfaces

The existing conversion flow is centered on `POST /conversions` and a one-shot request.

That is enough for immediate execution, but it is not enough for:

- inspection before conversion
- reusable configs
- saved drafts
- capability-driven editors
- spec migration over time

## New Backend Capabilities To Track

### 1. Inspection APIs

Needed so the frontend can inspect assets before building a spec.

Likely surfaces:

- topic inspection for one or more assets
- field-level inspection for a chosen topic
- draft-spec generation from inspection results
- preview for a draft spec

### 2. Capability Metadata APIs

Needed so the frontend can render authoring controls from backend-owned contracts instead of hard-coded enums.

Capability payloads should expose:

- supported row strategies
- supported feature source kinds
- supported transform kinds and required params
- supported dtypes
- current spec version
- supported migration paths
- preview defaults and limits

### 3. Reusable Config Resources

Needed so users can save and reuse authoring work.

Suggested persisted concepts:

- saved conversion config
- starter template reference
- draft revision
- preview summary for the latest draft

### 4. Spec Migration On Load

Needed so older saved configs do not silently drift out of compatibility.

The backend should:

- store the authored spec payload and spec version
- call into `hephaes` migration helpers when loading older configs
- surface upgrade notes back to the caller

## Data Model Changes To Track

The current backend uses JSON-backed structures in several places, so this can likely start with JSON payloads before aggressive normalization.

Potential new persisted entities:

### `conversion_configs`

- `id`
- `name`
- `description`
- `spec_json`
- `spec_version`
- `source_kind`
- `created_from_template`
- `created_from_inspection`
- `created_at`
- `updated_at`

### `conversion_config_drafts`

- `id`
- `conversion_config_id`
- `draft_spec_json`
- `base_spec_version`
- `preview_summary_json`
- `status`
- `created_at`
- `updated_at`

### Optional later metadata

- tags
- ownership fields
- soft archive state
- last successful conversion reference

## API Surface To Track

Exact route names can change, but the backend will likely need a split between authoring APIs and execution APIs.

### Authoring

- `GET /conversion-capabilities`
- `POST /conversion-inspections/topics`
- `POST /conversion-inspections/fields`
- `POST /conversion-drafts`
- `POST /conversion-drafts/preview`

### Reusable configs

- `GET /conversion-configs`
- `POST /conversion-configs`
- `GET /conversion-configs/{config_id}`
- `PATCH /conversion-configs/{config_id}`
- `POST /conversion-configs/{config_id}/duplicate`
- `POST /conversion-configs/{config_id}/drafts`

### Execution

- keep `POST /conversions`
- allow execution from either an inline spec or a saved config reference

## Service-Level Changes To Track

Likely backend service additions:

- inspection service
- draft-spec service
- capability service
- conversion-config persistence service
- migration helper path that delegates to `hephaes`

Likely updates to existing services:

- `app/services/conversions.py`
- `app/services/jobs.py`
- `app/services/outputs.py`

## File Areas Likely To Change Later

- `backend/app/db/models.py`
- `backend/app/schemas/conversions.py`
- `backend/app/schemas/`
- `backend/app/api/conversions.py`
- `backend/app/api/`
- `backend/app/services/conversions.py`
- `backend/app/services/`
- `backend/tests/`
- `backend/design/data-model-and-storage.md`
- `backend/design/jobs-conversions-playback-and-visualization.md`

## Phased Task List

### Phase 1: Contract and persistence planning

- [ ] Define saved-config and draft-revision backend schemas.
- [ ] Decide whether saved configs start as JSON-backed rows or another lightweight persistence model.
- [ ] Define the capability metadata contract the frontend will consume.

### Phase 2: Authoring APIs

- [ ] Add inspection request and response contracts.
- [ ] Add draft-spec request and response contracts.
- [ ] Add preview request and response contracts.
- [ ] Ensure these APIs delegate to `hephaes` business logic.

### Phase 3: Reusable config APIs

- [ ] Add create, read, update, duplicate, and list flows for saved configs.
- [ ] Add draft revision persistence if drafts need their own lifecycle.
- [ ] Add execution flow from a saved config reference.

### Phase 4: Migration and lifecycle

- [ ] Add spec-version tracking.
- [ ] Add migration on load through `hephaes`.
- [ ] Surface upgrade notes and invalid-config errors consistently.

### Phase 5: Test coverage

- [ ] Add API tests for inspection, drafting, preview, and saved-config CRUD.
- [ ] Add migration tests for stale saved specs.
- [ ] Add end-to-end tests for execute-from-saved-config behavior.

## Risks

- Duplicating converter semantics in backend services would create drift from `hephaes`.
- Saved configs will become brittle unless spec versioning and migration are handled centrally.
- Preview can become expensive if it shares the same lifecycle as full conversion runs.
- API shapes that mix authoring and execution concerns too aggressively will be hard to reason about.

## Acceptance Criteria

- The backend exposes stable authoring APIs without embedding converter heuristics in service code.
- Users can save, reload, and reuse conversion configs through backend-owned resources.
- Older saved configs can be migrated through `hephaes` rules.
- Conversion execution can run from either inline specs or saved config references.
