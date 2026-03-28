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
- a `Workspace` package API with durable local SQLite state
- asset registration, indexing, tags, saved configs, config revisions, draft heads, public draft lookup/state primitives, draft revision persistence, jobs, conversion runs, and outputs
- CLI commands for workspace init, asset add/index/list, inspect, convert, configs, jobs, runs, and outputs

What it does **not** yet contain is a package-owned end-to-end authoring workflow through `Workspace` and the CLI.

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
- asset registration/import/indexing
- tag creation and assignment
- saved config create/list/get/update/duplicate
- saved config revision history
- draft head create/list/get/resolve primitives
- draft revision record/list/get
- low-level draft state transition helpers
- job lifecycle
- conversion run lifecycle
- output artifact registration/list/get
- `run_conversion(...)`

Current role:

- `Workspace` owns durable state
- `Workspace` does **not** yet own the full authoring workflow

### Current CLI

Implemented commands include:

- `hephaes init`
- `hephaes add`
- `hephaes index`
- `hephaes ls assets`
- `hephaes inspect`
- `hephaes convert`
- `hephaes configs ...`
- `hephaes jobs ...`
- `hephaes runs ...`
- `hephaes outputs ...`

Missing:

- no `drafts` command group
- no interactive wizard

## Current Authoring Workflow Status

### 1. Source asset selection

Status: implemented

Package support today:

- assets can be registered into the workspace
- assets can be indexed
- workspace asset selectors already exist

Relevant files:

- `src/hephaes/workspace/assets.py`
- `src/hephaes/workspace/indexing.py`
- `src/hephaes/cli/commands/assets.py`

### 2. Inspect asset

Status: partially implemented

Implemented today:

- inspection helpers exist in `hephaes.conversion.introspection`
- CLI command `hephaes inspect` exists

Missing today:

- no `Workspace.inspect_asset(...)`
- no package-owned workflow method that resolves an asset and opens the reader internally for authoring

Relevant files:

- `src/hephaes/conversion/introspection.py`
- `src/hephaes/cli/commands/inspect.py`

### 3. Create draft spec from inspection

Status: partially implemented

Implemented today:

- `build_draft_conversion_spec(...)` exists
- draft revisions can be persisted with `record_conversion_draft_revision(...)`
- the current draft revision write path now creates a linked draft head row in `conversion_drafts`
- public `Workspace` draft lookups now resolve draft heads plus current/confirmed revisions

Missing today:

- no `Workspace.create_conversion_draft(...)`
- no package-owned method that runs inspect + draft + persistence as one workflow

Important current limitation:

- draft storage is now head-based, but the authoring workflow itself is still not package-owned

Relevant files:

- `src/hephaes/conversion/draft_spec.py`
- `src/hephaes/workspace/drafts.py`
- `src/hephaes/workspace/models.py`

### 4. Revise draft

Status: partially implemented at the persistence layer

Implemented today:

- one draft can own multiple immutable revision rows
- draft heads track `current_revision_id`
- internal workspace helpers exist to append revisions and move the current revision pointer

Missing today:

- no public `Workspace.update_conversion_draft(...)`
- no package-owned validation around what edits are allowed
- no high-level workflow method that appends a new revision and manages confirmation state

### 5. Preview draft

Status: partially implemented

Implemented today:

- preview helpers exist
- preview payloads can be stored on draft revision rows

Missing today:

- no `Workspace.preview_conversion_draft(...)`
- no package-owned preview workflow that operates on a draft entity
- no preview request persistence separate from preview result

Relevant files:

- `src/hephaes/conversion/preview.py`
- `src/hephaes/workspace/drafts.py`

### 6. Confirm draft

Status: partially implemented at the persistence layer

Implemented today:

- draft heads track `confirmed_revision_id`
- draft status values include `confirmed`
- internal state-transition helpers and draft lifecycle errors now exist

Missing today:

- no public confirmation API
- no lifecycle rule requiring preview before confirmation
- no package-owned confirmation workflow

### 7. Save confirmed draft as reusable config

Status: partially implemented, but not as draft promotion

Implemented today:

- generic saved config persistence exists

Missing today:

- no `save_conversion_config_from_draft(...)`
- no promotion from a confirmed draft
- no durable lineage from saved config back to draft and confirmed revision

Relevant files:

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

Current limitation:

- the package still does not expose high-level authoring workflow methods
- inspect, draft generation, preview, confirmation, and config promotion are not yet orchestrated through public `Workspace` methods

So the structural gap has narrowed from "no draft head exists" to "draft heads and low-level lifecycle primitives exist, but the public workflow still does not operate on them end-to-end."

## Current CLI State

### What exists

The CLI already supports:

- workspace bootstrapping
- asset ingestion/indexing
- ad hoc inspection
- saved config CRUD
- conversion execution

### What is missing

The CLI does **not** yet support:

- `drafts create`
- `drafts ls`
- `drafts show`
- `drafts update`
- `drafts preview`
- `drafts confirm`
- `drafts discard`
- `drafts save-config`
- `drafts wizard`

The required interactive wizard does not exist yet.

## Current Package Boundary

### Already package-owned

- local SQLite workspace
- authoring helper algorithms
- config persistence
- conversion execution
- run/output tracking

### Not yet package-owned in the right form

- authoring orchestration across inspect -> draft -> preview -> confirm -> save
- draft lifecycle semantics
- CLI-first authoring UX

## Known Gaps Relative To The Target Design

The target design in `design/architecture.md` and `design/implementation.md` is **not** implemented yet.

Main gaps:

- no `Workspace.inspect_asset(...)`
- no `Workspace.create_conversion_draft(...)`
- no `Workspace.update_conversion_draft(...)`
- no `Workspace.preview_conversion_draft(...)`
- no `Workspace.confirm_conversion_draft(...)`
- no `Workspace.save_conversion_config_from_draft(...)`
- no `Workspace.discard_conversion_draft(...)`
- no `drafts` CLI command group
- no required interactive wizard

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

- package-owned inspect/draft/preview workflow methods
- draft confirmation rules
- draft promotion to saved config
- wizard behavior

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
- full package-owned authoring workflow does not yet exist
