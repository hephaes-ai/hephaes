# Hephaes Local Core Implementation Plan

## Outcome

Make `hephaes` a standalone local app core that can be used directly from Python or through the CLI, with `Workspace` as the only public entry point.

The package should own local imports, persistence, and high-level workflows. Visualization and replay remain out of scope for this implementation plan.

## Guiding Rules

- Keep `Workspace` as the only public entry point.
- Design package APIs for direct Python and CLI use.
- Keep imports workspace-managed.
- Keep job and run associations JSON-backed in the initial implementation.
- Defer `output_actions` until there is a concrete standalone use case.
- Land the work in phases that leave the package usable after each step.

## Phase 1: Workspace Layout and Schema Foundation

### Goals

- Expand the workspace layout to support the standalone local app model.
- Add the durable schema needed for the missing local domain concepts.

### Tasks

- Extend workspace layout to include `.hephaes/imports/`.
- Update workspace path modeling to include imports.
- Add schema and migrations for:
  - tags
  - asset-tag associations
  - config revisions
  - draft revisions
  - jobs
  - conversion runs
- Do not add `output_actions` in this phase.
- Extend workspace dataclasses in `hephaes/src/hephaes/_workspace_models.py`.
- Extend row serialization helpers in `hephaes/src/hephaes/_workspace_serialization.py`.
- Add migration tests for existing workspace versions.

### Exit Criteria

- A workspace can be initialized or opened with the new layout.
- `.hephaes/imports/` exists for newly initialized workspaces.
- New durable state persists correctly in `.hephaes/workspace.sqlite3`.

## Phase 2: Asset Imports, Catalog, Indexing, and Tags

### Goals

- Make asset ingestion and asset management fully workspace-owned.

### Tasks

- Add workspace-managed import APIs such as:
  - `import_asset`
  - optional batch import helpers if they are useful for CLI workflows
- Define import behavior:
  - copy or stage files into `.hephaes/imports/`
  - record original source path as provenance metadata when useful
  - define duplicate handling clearly
- Update asset listing to support filters.
- Add tag APIs:
  - `list_tags`
  - `create_tag`
  - `attach_tag_to_asset`
  - `remove_tag_from_asset`
- Ensure indexing works cleanly against imported workspace assets.
- Add package tests for import, deduplication, indexing, filtering, and tagging.

### Exit Criteria

- The canonical asset workflow is import into the workspace.
- Assets, indexed metadata, filters, and tags are all package-owned.
- Core asset workflows feel coherent when used directly from Python.

## Phase 3: Saved Configs and Draft Revisions

### Goals

- Move saved config lifecycle and authoring persistence fully into the workspace model.

### Tasks

- Add saved config APIs for:
  - create
  - get
  - list
  - update
  - duplicate
- Add revision listing and retrieval helpers.
- Add draft revision recording and retrieval helpers.
- Preserve migration-on-load behavior for spec documents.
- Add package tests for:
  - create
  - update
  - duplicate
  - migration-on-load
  - revision history
  - draft persistence

### Exit Criteria

- Saved configs, revisions, and draft revisions are fully package-owned.
- `Workspace` supports the complete saved-config lifecycle without external helpers.

## Phase 4: Jobs, Conversion Runs, and Outputs

### Goals

- Add the operational state needed for standalone conversion workflows.

### Tasks

- Add durable job APIs:
  - create
  - list
  - get
  - mark running
  - mark succeeded
  - mark failed
- Keep job associations JSON-backed.
- Add durable conversion run APIs:
  - create pending run
  - list
  - get
  - mark running
  - mark succeeded
  - mark failed
- Keep run associations and config snapshots JSON-backed.
- Update `Workspace.run_conversion()` to create and update a durable conversion run record.
- Make output artifact registration explicitly tied to conversion runs.
- Add output listing, lookup, and metadata refresh APIs.
- Explicitly defer output actions from this phase.
- Add package tests for conversion lifecycle, job lifecycle, and output registration.

### Exit Criteria

- Standalone conversion workflows are fully represented in workspace state.
- Jobs, conversion runs, and outputs are package-owned and queryable.

## Phase 5: Dashboard and Query Helpers

### Goals

- Add useful read/query APIs over workspace-owned state.

### Tasks

- Add asset query helpers needed for CLI and direct Python use.
- Add dashboard-style aggregation helpers such as:
  - summary counts
  - trend buckets
  - blocker counts
- Keep these query helpers internal to `Workspace` rather than exposing a separate public query service.
- Add package tests for empty and populated workspaces.

### Exit Criteria

- `Workspace` can answer common operational questions without external query layers.
- Query helpers remain part of the single-entry-point package model.

## Phase 6: Public API and CLI Polish

### Goals

- Make the resulting package feel good to use directly.

### Tasks

- Audit `Workspace` method names and exceptions for direct Python ergonomics.
- Ensure the CLI maps closely to `Workspace` operations.
- Add package-level usage docs and examples for:
  - workspace initialization
  - importing assets
  - indexing
  - saving configs
  - running conversions
  - inspecting outputs
- Verify that internal modules remain private and that `Workspace` is the only intended public workflow entry point.

### Exit Criteria

- The main workflows are easy to discover from Python and CLI.
- The package boundary is clear and small.

## Phase 7: Package Boundary Documentation

### Goals

- Make the package boundary explicit without expanding the implementation scope.

### Tasks

- Document `Workspace` as the only public entry point.
- Document visualization and replay as out-of-scope layers.
- Document why output actions were deferred.

### Exit Criteria

- The package architecture is understandable without relying on any external app layer.

## Recommended Slice Order

1. workspace layout and schema foundation
2. asset imports, catalog, indexing, and tags
3. saved configs and draft revisions
4. jobs, conversion runs, and outputs
5. dashboard and query helpers
6. public API and CLI polish
7. package boundary documentation

## Validation Checklist

Each phase should include:

- package tests for newly added domain logic
- workspace migration tests where schema changes occur
- direct Python smoke checks for the newly added workflows
- CLI smoke checks for any mapped commands

## Main Risks

### Public API drift

Mitigation:
Continuously audit `Workspace` for direct-use ergonomics rather than letting internal implementation details leak into the public surface.

### Import semantics become unclear

Mitigation:
Define canonical import behavior early, especially around provenance, naming, and duplicates.

### Under-modeling conversion runs

Mitigation:
Treat conversion runs as first-class durable records before relying on `Workspace.run_conversion()` as the main workflow API.

### Overloading the initial schema

Mitigation:
Keep JSON-backed associations where they are sufficient, and defer less-proven features such as output actions.
