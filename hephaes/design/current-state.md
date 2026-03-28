# Current Package State

## Purpose

This file is a working implementation snapshot for `hephaes` itself.

It is meant to help implementation agents answer:

- what is already implemented in the package
- what parts of the authoring workflow are package-owned today
- what parts are still missing relative to the target architecture
- which package files are the main implementation anchors

This document is package-focused. It intentionally does not treat the backend as the source of truth for workflow behavior.

## Snapshot

As of `2026-03-28`, `hephaes` already contains:

- pure conversion authoring helpers for inspect, draft generation, and preview
- a `Workspace` package API with durable local SQLite state and package-owned authoring workflow methods through config promotion
- linked-path asset registration, indexing, tags, saved configs, config revisions, draft heads, public draft lookup/state primitives, draft revision persistence, jobs, conversion runs, and outputs
- CLI commands for workspace init, asset add/index/list, inspect, drafts, drafts wizard, convert, configs, jobs, runs, and outputs

The core package-owned authoring workflow is now implemented through both `Workspace` and the CLI.

## Redesign Progress

The current redesign target is:

- keep local `.hephaes` workspaces rooted in the user's chosen working directory
- remove copied-asset storage from the workspace
- make registered asset paths the only source used by indexing, authoring, and conversion

Current phase status:

- Phase 1 complete: the package already matches the desired local workspace baseline
- Phase 2 complete: assets are now linked by path and the workspace no longer creates `.hephaes/imports`
- Phase 3 complete: runtime path-availability errors are now package-owned across index, inspect, drafts, and convert
- Phase 4 complete: package cleanup removed the last copy helper and remaining CLI wording now reflects registered file paths
- Phase 5 complete: package tests, docs build, and a real-file CLI smoke test all validated the linked-path workspace model

## Current Package Surface

### Pure authoring helpers in `hephaes.conversion`

Implemented:

- `inspect_reader(...)`
- `inspect_bag(...)`
- `build_draft_conversion_spec(...)`
- `preview_conversion_spec(...)`
- `preflight_conversion_spec(...)`
- conversion spec I/O and migration helpers

Current role:

- these are stateless helpers
- they do not own workspace state
- they do not own draft lifecycle rules

### Durable package API in `hephaes.workspace`

Implemented through `Workspace` mixins:

- workspace init/open
- linked-path asset registration and indexing
- tag creation and assignment
- saved config create/list/get/update/duplicate
- saved config revision history
- draft head create/list/get/resolve primitives
- draft revision record/list/get
- low-level draft state transition helpers
- package-owned `inspect_asset(...)`
- package-owned `create_conversion_draft(...)`
- package-owned `update_conversion_draft(...)`
- package-owned `preview_conversion_draft(...)`
- package-owned `confirm_conversion_draft(...)`
- package-owned `discard_conversion_draft(...)`
- package-owned `save_conversion_config_from_draft(...)`
- job lifecycle
- conversion run lifecycle
- output artifact registration/list/get
- `run_conversion(...)`

Current role:

- `Workspace` owns durable state
- `Workspace` now owns inspect -> draft -> preview -> confirm -> save authoring flow
- `Workspace` does **not** yet own the CLI UX

### Current CLI

Implemented commands include:

- `hephaes init`
- `hephaes add`
- `hephaes index`
- `hephaes ls assets`
- `hephaes inspect`
- `hephaes drafts ...`
- `hephaes drafts wizard ...`
- `hephaes convert`
- `hephaes configs ...`
- `hephaes jobs ...`
- `hephaes runs ...`
- `hephaes outputs ...`

Missing:

- no major command gaps for the authoring workflow

## Current Authoring Workflow Status

### 1. Source asset selection

Status: implemented

Package support today:

- assets can be registered into the workspace
- assets can be indexed
- workspace asset selectors already exist

Important current behavior:

- the workspace now stores the normalized source file path directly on the asset record
- assets are no longer copied into `.hephaes/imports`
- registered asset paths are validated before indexing, authoring, and conversion work begins

Relevant files:

- `src/hephaes/workspace/assets.py`
- `src/hephaes/workspace/indexing.py`
- `src/hephaes/cli/commands/assets.py`

### 2. Inspect asset

Status: implemented

Implemented today:

- inspection helpers exist in `hephaes.conversion.introspection`
- `Workspace.inspect_asset(...)` resolves the asset and opens the reader internally
- CLI command `hephaes inspect` exists

Missing today:

- standalone `inspect` still calls `inspect_bag(...)` directly instead of reusing `Workspace.inspect_asset(...)`

Important current behavior:

- CLI inspect path resolution now validates the registered asset path first when the selector matches a workspace asset
- missing registered asset files now fail with a workspace-level asset-unavailable error instead of falling through to a generic reader/path failure

Relevant files:

- `src/hephaes/conversion/introspection.py`
- `src/hephaes/cli/commands/inspect.py`

### 3. Create draft spec from inspection

Status: implemented through `Workspace`

Implemented today:

- `build_draft_conversion_spec(...)` exists
- draft revisions can be persisted with `record_conversion_draft_revision(...)`
- the current draft revision write path now creates a linked draft head row in `conversion_drafts`
- public `Workspace` draft lookups now resolve draft heads plus current/confirmed revisions
- `Workspace.create_conversion_draft(...)` runs inspect + draft + persistence as one package-owned flow

Missing today:

- standalone `inspect` is still separate from the draft-first CLI flow

Important current limitation:

- standalone `inspect` still remains a separate CLI path outside the draft-first flow

Relevant files:

- `src/hephaes/conversion/draft_spec.py`
- `src/hephaes/workspace/drafts.py`
- `src/hephaes/workspace/models.py`

### 4. Revise draft

Status: implemented through `Workspace`

Implemented today:

- one draft can own multiple immutable revision rows
- draft heads track `current_revision_id`
- internal workspace helpers exist to append revisions and move the current revision pointer
- `Workspace.update_conversion_draft(...)` appends a new immutable revision and resets confirmation when needed

Missing today:

- no in-wizard text editor; updates still point at spec document paths

### 5. Preview draft

Status: implemented through `Workspace`

Implemented today:

- preview helpers exist
- preview payloads can be stored on draft revision rows
- `Workspace.preview_conversion_draft(...)` opens the source asset reader, runs preview, and persists preview request/result state

Missing today:

- no additional preview-specific wizard controls beyond sample count

Relevant files:

- `src/hephaes/conversion/preview.py`
- `src/hephaes/workspace/drafts.py`

### 6. Confirm draft

Status: implemented through `Workspace`

Implemented today:

- draft heads track `confirmed_revision_id`
- draft status values include `confirmed`
- internal state-transition helpers and draft lifecycle errors now exist
- `Workspace.confirm_conversion_draft(...)` requires a successful current preview before confirmation

Missing today:

- no major package gap in this workflow step

### 7. Save confirmed draft as reusable config

Status: implemented through `Workspace`

Implemented today:

- generic saved config persistence exists
- `Workspace.save_conversion_config_from_draft(...)` promotes a confirmed draft into a saved config
- promoted configs carry draft lineage in config metadata
- confirmed draft revisions are linked to the saved config id and draft status moves to `saved`

Missing today:

- saved config lineage is currently surfaced through config metadata rather than dedicated config fields

Relevant files:

- `src/hephaes/workspace/drafts.py`
- `src/hephaes/workspace/configs/mutations.py`
- `src/hephaes/workspace/configs/queries.py`
- `src/hephaes/workspace/configs/revisions.py`

### 8. Run conversion from saved config

Status: implemented

Implemented today:

- `Workspace.run_conversion(...)` supports execution from a saved config selector
- conversion runs, jobs, and outputs are persisted

Important notes:

- this is already package-owned
- the method currently sits after config creation, not after draft confirmation/promotion

Relevant files:

- `src/hephaes/workspace/conversions.py`
- `src/hephaes/workspace/outputs.py`
- `src/hephaes/workspace/jobs.py`
- `src/hephaes/cli/commands/convert.py`

## Current Data Model State

### Implemented durable tables/concepts

The workspace currently includes durable state for:

- assets
- asset metadata
- tags
- saved conversion configs
- saved config revisions
- conversion drafts
- conversion draft revisions
- jobs
- conversion runs
- output artifacts

### Current draft-head state

The package now has a `conversion_drafts` table and public draft-head models:

- `ConversionDraftSummary`
- `ConversionDraft`

Current behavior:

- legacy draft revisions migrate forward into one draft head per legacy row
- new calls to `record_conversion_draft_revision(...)` create one draft head plus one revision row
- public draft listings now support filters by status, source asset, and saved config
- draft lookups now resolve current and confirmed revisions through `ConversionDraft`
- high-level `Workspace` methods now orchestrate create/update/preview/confirm/discard on top of those primitives
- draft promotion now links confirmed revisions to saved configs and stores lineage in saved config metadata

Current limitation:

- the wizard is intentionally lightweight and relies on external spec-document edits for manual revision changes

So the structural gap has narrowed from "no draft head exists" to "the package-owned workflow is implemented, with remaining work mostly in validation depth and docs polish."

## Current CLI State

### What exists

The CLI already supports:

- workspace bootstrapping
- asset ingestion/indexing
- ad hoc inspection
- scriptable draft authoring commands
- interactive draft authoring through `drafts wizard`
- saved config CRUD
- conversion execution

### What is missing

No major target-workflow command gaps remain.

## Current Package Boundary

### Already package-owned

- local SQLite workspace
- authoring helper algorithms
- config persistence
- conversion execution
- run/output tracking

### Not yet package-owned in the right form

- standalone inspect still bypasses `Workspace.inspect_asset(...)`
- some lineage/query surfacing still lives in config metadata instead of dedicated fields

## Known Gaps Relative To The Target Design

The target design in `design/architecture.md` and `design/implementation.md` is **not** implemented yet.

Main gaps:

- standalone `inspect` still bypasses `Workspace.inspect_asset(...)`
- lineage surfacing still depends on config metadata
- some future polish could move lineage/query surfacing into dedicated fields if needed

## Main Implementation Anchors

These are the package files most likely to change during the implementation.

### Core workspace schema and models

- `src/hephaes/workspace/schema.py`
- `src/hephaes/workspace/models.py`
- `src/hephaes/workspace/serialization.py`
- `src/hephaes/workspace/errors.py`

### Draft/config workflow

- `src/hephaes/workspace/drafts.py`
- `src/hephaes/workspace/configs/mutations.py`
- `src/hephaes/workspace/configs/queries.py`
- `src/hephaes/workspace/configs/revisions.py`
- `src/hephaes/workspace/api.py`
- `src/hephaes/workspace/__init__.py`

### Pure helpers that should remain reusable

- `src/hephaes/conversion/introspection.py`
- `src/hephaes/conversion/draft_spec.py`
- `src/hephaes/conversion/preview.py`
- `src/hephaes/conversion/spec_io.py`

### CLI

- `src/hephaes/cli/parser.py`
- `src/hephaes/cli/commands/inspect.py`
- `src/hephaes/cli/commands/configs.py`
- `src/hephaes/cli/commands/convert.py`
- `src/hephaes/cli/commands/workspace.py`
- `src/hephaes/cli/commands/drafts.py` (new)

## Test State

Relevant package tests already exist for:

- workspace persistence
- saved config lifecycle
- draft-head schema/migration compatibility
- draft-head lookup and state primitive behavior
- workspace-owned inspect/create/update/preview/confirm/discard authoring flow
- workspace-owned draft promotion and lineage
- scriptable CLI draft workflow
- interactive draft wizard flow
- wizard cancel-before-save and resume behavior
- draft revision persistence
- conversion authoring helpers
- conversion execution

Relevant test files:

- `tests/test_workspace.py`
- `tests/test_conversion_authoring.py`

Observed during implementation on `2026-03-28`:

- `pytest hephaes/tests/test_workspace.py hephaes/tests/test_package_init.py` passed
- `pytest hephaes/tests` passed

What is not covered yet:

- no major workflow gaps remain; future work is mostly incremental polish

## Working Assumptions For Implementation

- the backend can be ignored while implementing package-owned workflow behavior
- the CLI wizard is required
- scriptable CLI commands are still required for testing and automation
- pure conversion helpers should stay stateless
- durable authoring workflow logic should move into `Workspace`

## Definition Of "Current State" For Agents

If an implementation agent needs a quick rule of thumb:

- use `design/architecture.md` for the target shape
- use `design/implementation.md` for the phased rollout
- use this file for what is true in the package right now

Current shorthand:

- authoring primitives exist
- durable workspace exists
- draft-head persistence primitives now exist
- `Workspace` owns inspect -> draft -> preview -> confirm -> save
- scriptable CLI authoring exists
- the required wizard exists
