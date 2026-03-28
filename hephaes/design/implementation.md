# Local Workspace And Linked-Asset Implementation Plan

## Objective

Implement a simpler local package model for `hephaes` with these rules:

- the user creates a local workspace with `hephaes init`
- that workspace lives in `.hephaes/` under the current directory or chosen root
- assets are registered by absolute path only
- the package never copies raw assets into workspace storage
- indexing, inspection, drafts, preview, and conversion all use the registered source path

This is a breaking reset for asset handling, but it keeps the current local workspace shape.

## Delivery Rules

- Do not preserve the old copied-asset workflow.
- Keep local `.hephaes` workspaces and path-based workspace selection.
- Keep `Workspace` as the durable package boundary.
- Keep the CLI as a thin adapter over package-owned workspace logic.
- Prefer deleting obsolete copy/import behavior rather than layering new modes on top of it.

## Core Assumptions

### Fresh workspaces only

We are not planning a migration path from older copied-asset workspaces.

The expected path is:

1. install the updated package
2. create a fresh local workspace
3. re-register asset paths

### One asset model

There is only one asset registration mode:

- linked path registration

There is no copied/imported asset mode.

### Local workspace roots remain

Workspaces continue to live at:

```text
<chosen-root>/.hephaes
```

## Phase Summary

| Phase | Outcome |
| --- | --- |
| 1 | Local workspace baseline is locked to the simplified model |
| 2 | Asset schema is reset around linked file paths |
| 3 | Indexing, inspect, drafts, and conversion use registered paths end to end |
| 4 | Old copy/import assumptions are removed from the package and CLI |
| 5 | Tests, docs, and smoke validation cover the new model |

## Progress Tracking

| Phase | Status | Notes |
| --- | --- | --- |
| 1 | completed | Confirmed the existing package already matches the target local `.hephaes` workspace baseline; no home-directory workspace-manager work is needed. |
| 2 | completed | Removed `imports/` from the workspace layout, simplified the asset schema around `file_path`, switched registration to linked source paths, and made older workspace schema versions fail clearly. |
| 3 | completed | Added package-owned registered-path validation, introduced clear asset-unavailable errors, and wired index, inspect, drafts, and convert through the validated linked-path flow. |
| 4 | pending | Copy/import cleanup and CLI wording updates have not landed yet. |
| 5 | pending | Final tests, docs refresh, and smoke validation have not landed yet. |

## Phase 1: Local Workspace Baseline

### Goal

Keep the current local `.hephaes` workspace model and remove any broader workspace-manager ambitions from the implementation plan.

### Status

Completed on `2026-03-28`.

### Tasks

- Keep `Workspace.init(root)` rooted at a filesystem directory and producing `<root>/.hephaes`.
- Keep `Workspace.open(root=None)` based on:
  - explicit filesystem path when provided
  - otherwise upward `.hephaes` discovery from the current directory
- Remove any design assumptions about:
  - home-directory workspace registries
  - active workspace config
  - named workspaces
- Update `WorkspacePaths` to reflect the simplified local layout.
- Remove `imports_dir` from `WorkspacePaths`.
- Remove workspace layout creation for `imports/`.
- Decide how the package should handle older workspaces that still contain copied-asset data:
  - reject them clearly
  - or require re-init and treat them as out of contract

### Notes

- The current package already uses local `.hephaes` workspaces rooted at the chosen directory.
- Upward workspace discovery already exists and remains in scope.
- `imports/` removal is deferred to Phase 2 because the current asset registration path still depends on it.

### Exit Criteria

- the target implementation is clearly based on local `.hephaes` workspaces
- workspace init/open semantics stay path-based and local
- the package layout no longer reserves space for copied raw assets

## Phase 2: Linked-Asset Schema Reset

### Goal

Redefine assets as linked source files rather than copied workspace imports.

### Status

Completed on `2026-03-28`.

### Tasks

- Simplify the `assets` table to keep the original file path as the canonical runtime path.
- Remove copied-asset fields and assumptions from the asset schema, including:
  - `source_path`
  - `imported_at`
- Keep asset fields needed for durable package behavior:
  - `id`
  - `file_path`
  - `file_name`
  - `file_type`
  - `file_size`
  - `indexing_status`
  - `last_indexed_at`
  - `registered_at`
  - `updated_at`
- Refactor `RegisteredAsset` and related serialization code to match the new schema.
- Remove or collapse `import_asset(...)` so registration has one clear path-based flow.
- Remove copy helpers and import-destination builders from asset registration.
- Simplify duplicate registration behavior:
  - `error`
  - `skip`
  - `refresh`
- Make `refresh` update the recorded file metadata from the original path instead of copying bytes.
- Bump the workspace schema version and make the new schema authoritative for fresh linked-asset workspaces.

### Notes

- `WorkspacePaths` no longer includes `imports_dir`.
- The `assets` table now stores the normalized linked source path directly as `file_path`.
- `Workspace.register_asset(...)` no longer copies raw files into `.hephaes`.
- Older workspace schema versions are now rejected with a clear "create a fresh local workspace" error instead of being migrated.

### Exit Criteria

- new workspaces store only linked asset paths
- registering an asset never copies raw bytes into the workspace
- package models and schema match the linked-asset design

## Phase 3: Path-Based Runtime Behavior

### Goal

Ensure every package workflow uses the registered asset path as the source of truth.

### Status

Completed on `2026-03-28`.

### Tasks

- Add a shared asset-path validation helper in the workspace layer.
- Introduce a specific workspace error for missing or unavailable registered asset paths.
- Update indexing to open `asset.file_path` directly.
- Update standalone inspect path resolution to prefer registered asset paths from the selected workspace.
- Audit draft authoring methods so they always resolve an asset id to the stored path before opening readers.
- Audit conversion execution so saved-config and direct conversions both use the registered path when the source is a workspace asset.
- Ensure run and output lineage still records:
  - source asset id
  - source asset path
  - saved config id
- Add failure coverage for:
  - moved asset file
  - deleted asset file
  - unreadable asset file

### Notes

- The workspace now exposes a package-owned linked-path validation helper for registered assets.
- Missing registered files now raise a dedicated `AssetUnavailableError`.
- `index_asset(...)`, workspace authoring flows, conversion execution, and CLI inspect resolution now use the validated asset path instead of assuming the stored path is still usable.

### Exit Criteria

- indexing, inspect, drafts, preview, and conversion all use the stored registered path
- path availability failures are clear and package-owned
- no workflow still depends on copied asset files

## Phase 4: Package And CLI Cleanup

### Goal

Remove old terminology and code paths that imply local asset copying.

### Status

Completed on `2026-03-28`.

### Tasks

- Remove dead helpers related to asset copying and import destinations.
- Remove dead references to `imports_dir`.
- Update CLI help text from "upload/import into workspace" wording to "register/link".
- Update command output so asset displays are based on the canonical linked path.
- Review package modules for assumptions that `file_path` and `source_path` are distinct concepts.
- Remove docs and comments that describe copied raw assets inside `.hephaes`.
- Ensure examples consistently show:
  - `hephaes init`
  - `hephaes add /path/to/file`
  - later commands operating from the registered path-backed asset

### Notes

- The last unused workspace copy helper has been removed from the package.
- CLI help text now consistently refers to registered file paths rather than original import paths.

### Exit Criteria

- package code no longer describes or implies copied raw assets
- CLI wording matches the new linked-path model
- no package code still depends on `imports/`

## Phase 5: Tests, Docs, And Manual Validation

### Goal

Harden the redesign and document the new user model clearly.

### Status

Completed on `2026-03-28`.

### Tasks

- Update package tests for:
  - local workspace creation under `<root>/.hephaes`
  - linked asset registration
  - duplicate refresh without file copying
  - indexing from linked paths
  - inspect/draft/preview/convert from linked paths
  - missing linked asset failures
- Remove or rewrite tests that assume copied assets inside the workspace.
- Update `README.md` to describe:
  - local workspace creation
  - linked asset registration
  - path-based source handling
- Update published docs under `docs/` to match the new local workspace and linked-asset model.
- Update `hephaes/design/current-state.md` after implementation lands so it reflects the new reality instead of the pre-reset asset model.
- Run a manual smoke flow:
  1. `mkdir demo && cd demo`
  2. `hephaes init`
  3. `hephaes add ~/path/to/file.mcap`
  4. `hephaes inspect ...`
  5. `hephaes drafts wizard ...`
  6. `hephaes convert ...`
  7. `hephaes outputs ls`

### Notes

- `pytest hephaes/tests` passes with `374 passed`.
- `npm run build` in `docs/` succeeds with the updated linked-path documentation.
- A manual CLI smoke test against `/Users/danielyoo/Downloads/demo/optimal_0.mcap` confirmed `init`, `add`, `inspect`, `drafts create`, `drafts preview`, `drafts confirm`, and `drafts save-config` using the canonical registered file path without copying the raw asset.
- Conversion execution remains covered by the package test suite, including conversion runs from promoted saved configs.

### Exit Criteria

- tests reflect the new package contract
- docs describe the local workspace and linked-asset model clearly
- the end-to-end CLI flow works without copied assets

## Recommended Delivery Order

1. Phase 1: local workspace baseline
2. Phase 2: linked-asset schema reset
3. Phase 3: path-based runtime behavior
4. Phase 4: package and CLI cleanup
5. Phase 5: tests, docs, and manual validation

## Open Decisions To Settle Before Implementation

### Older workspace handling

Even though we are not supporting the old copied-asset model, implementation should still decide whether older workspaces are:

- rejected with a clear error
- or treated as unsupported and expected to be re-initialized

My recommendation is to fail clearly when an older incompatible workspace layout or schema is opened.

### Asset path normalization level

We should explicitly define whether the canonical stored path is:

- `expanduser + resolve(strict=False)`

or something slightly less aggressive.

My recommendation is to store a normalized absolute path using the same normalization behavior already used elsewhere in the workspace layer.
