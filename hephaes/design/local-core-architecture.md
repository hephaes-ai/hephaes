# Hephaes Local Core Architecture

## Decision

`hephaes` becomes the standalone local application core.

The package owns the local domain model, workspace persistence, and high-level workflows needed to use Hephaes directly from Python or via the CLI. `Workspace` is the only public entry point for this local application model.

This includes:

- workspace-managed asset imports
- asset catalog and indexing state
- tags
- saved conversion configs, revisions, and draft revisions
- conversion execution records
- output artifact cataloging
- dashboard-style aggregation queries
- durable local job tracking

This does not include:

- visualization preparation
- replay and streaming
- remote or multi-user concerns
- HTTP or UI adapter concerns

## Why

The package should be usable on its own, without requiring a frontend or any separate application layer.

That means the real local product logic cannot live outside the package. It needs to live in `hephaes` itself so that:

- a Python user can script workflows directly
- the CLI can remain a thin wrapper over package APIs
- other local consumers can call the same core

The target is not for `hephaes` to become adapter-shaped or frontend-driven. The target is for `hephaes` to become the standalone local product core.

## Goals

- Make `hephaes` the single source of truth for local persistent state.
- Keep the package natural to use from Python and CLI.
- Preserve the workspace-based local model.
- Make `Workspace` the clear top-level abstraction for local usage.
- Keep imports, durable state, and emitted outputs owned by the workspace.
- Keep the public package boundary small and stable.

## Non-Goals

- Rebuilding replay or visualization inside `hephaes` right now.
- Designing a remote or multi-user persistence model.
- Exposing a large set of public sub-services alongside `Workspace`.
- Designing APIs around HTTP payloads or route structure.

## Target Shape

```text
Python scripts
  -> hephaes.Workspace

CLI
  -> hephaes.Workspace
```

## Ownership Boundaries

### Owned by `hephaes`

- workspace discovery and initialization
- workspace-managed imports
- SQLite schema and migrations for local durable state
- domain validation and write rules
- asset catalog and indexed metadata
- conversion authoring persistence
- conversion execution history
- output catalog and metadata refresh logic
- query/filter helpers and dashboard aggregations
- durable job state transitions

### Outside `hephaes`

- visualization artifact generation
- replay transport and streaming behavior
- any future HTTP/UI adapter concerns

## Package Boundary

`Workspace` is the only public entry point for the local app model.

The intended public experience is:

- open or initialize a workspace
- import assets into that workspace
- inspect, tag, index, convert, and query through workspace methods

Internal implementation can be split across private modules, but those modules stay private. A likely internal structure is:

- `workspace.py`: public facade and composition root
- `_workspace_schema.py`: SQLite schema and migrations
- `_workspace_models.py`: durable dataclasses
- `_workspace_serialization.py`: row/dataclass conversion
- `_workspace_assets.py`: imports, assets, metadata, tags, filters
- `_workspace_configs.py`: saved configs, revisions, draft revisions
- `_workspace_runs.py`: conversion runs and output registration
- `_workspace_jobs.py`: job lifecycle
- `_workspace_queries.py`: dashboard and list/query helpers

This keeps the package organized while preserving a simple public surface.

## Workspace Layout

The workspace remains directory-scoped and self-contained under `.hephaes/`.

Target layout:

- `.hephaes/workspace.sqlite3`
- `.hephaes/imports/`
- `.hephaes/outputs/`
- `.hephaes/specs/`
- `.hephaes/jobs/`

### Imports

Imports are workspace-managed.

That means the canonical local asset files should live under `.hephaes/imports/`, and the main write path should be workspace import operations rather than external-path registration. Provenance such as the original source path can still be recorded in metadata, but the workspace owns the imported copy.

## Workspace-Owned Data Model

The workspace database should own all local durable state except visualization/replay caches.

### Core tables

- `workspace_meta`
- `assets`
- `asset_metadata`
- `tags`
- `asset_tags`
- `conversion_configs`
- `conversion_config_revisions`
- `conversion_draft_revisions`
- `jobs`
- `conversion_runs`
- `output_artifacts`

### Modeling note

For the initial implementation, keep job and run associations JSON-backed where that is simpler and already fits the shape of the data.

Examples:

- `jobs.target_asset_ids_json`
- `jobs.config_json`
- `conversion_runs.source_asset_ids_json`
- `conversion_runs.config_json`

If query complexity grows later, those can be normalized in a follow-up pass.

## API Direction

The public workspace API should express local domain operations, not route-shaped wrappers.

Representative operations:

- initialize or open a workspace
- import assets into the workspace
- list/filter assets
- index assets
- create/list/attach/detach tags
- create/get/list/update/duplicate saved configs
- record and inspect revisions and draft revisions
- create and inspect jobs
- create and inspect conversion runs
- execute conversions
- register and list output artifacts
- query dashboard-style summaries

API design rule:

- methods should read naturally from Python
- the CLI should map closely to those methods

## Job Model

Jobs are durable workspace state.

The workspace owns:

- job creation
- state transitions
- timestamps
- lightweight config payloads
- links to assets and conversion runs

The initial design keeps job associations JSON-backed, which is acceptable for the current scope and keeps the schema simpler.

## Conversion Run Model

`Workspace.run_conversion()` is a useful convenience API, but the workspace should also persist a first-class conversion run record.

A conversion run should capture:

- run id
- linked job id if applicable
- source asset ids
- saved config id and revision metadata when applicable
- execution status
- output directory
- output file paths
- error state
- created and updated timestamps

Output artifacts should reference this conversion run record.

## Output Artifacts

Output artifacts are the durable catalog of emitted files under the workspace outputs area.

They should capture:

- owning conversion run
- relative path
- file name
- format
- role
- media type
- availability status
- summary metadata
- created and updated timestamps

## Output Actions

An output action is a post-processing operation attached to an already-generated output artifact.

Examples of what that could mean:

- refresh stored metadata for an output file
- validate a produced file
- generate a derivative sidecar from an existing output

Right now this concept is not central to the standalone package story, and there is not yet a strong set of concrete package-level use cases for it. Because of that, output actions are deferred from the initial architecture rather than treated as a core table from day one.

## Benefits

- one clear local application core
- one durable store for local state
- one domain model shared by Python scripts, CLI, and future local adapters
- easier package-level testing of real workflows
- simpler path toward future local app integrations

## Risks and Guardrails

### Risk: package scope creep

Guardrail:
Move local domain logic and persistence only. Keep visualization, replay, and adapter concerns out.

### Risk: package becomes hard to use directly

Guardrail:
Keep `Workspace` ergonomic and high-level for direct Python use.

### Risk: oversized `Workspace`

Guardrail:
Keep `Workspace` as the only public entry point, but split implementation across internal private modules.

### Risk: under-modeling imports or conversion runs

Guardrail:
Treat workspace-managed imports and first-class conversion runs as foundational parts of the architecture, not optional extras.

## Resolved Decisions

- `Workspace` is the only public entry point.
- Imports are workspace-managed under `.hephaes/imports/`.
- Job and run payload associations remain JSON-backed in the initial model.
- `output_actions` are deferred until there is a concrete standalone package use case.
