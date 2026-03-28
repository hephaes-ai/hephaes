# Local Workspace And Linked-Asset Architecture

## Goal

Keep the current local workspace shape, but simplify asset handling:

1. the user runs `hephaes init` in the directory they want to use
2. that directory gets a local `.hephaes/` workspace
3. adding an asset stores its normalized absolute file path in the workspace database
4. indexing, inspection, draft authoring, preview, and conversion all use that stored path
5. raw assets are never copied into the workspace

This is still a breaking reset for asset storage, but it is not a full redesign of where workspaces live.

## Breaking Direction

This change is intentionally breaking for asset handling.

We are explicitly **not** designing for compatibility with:

- old copied/imported asset records
- mixed linked-asset and copied-asset modes

The expected upgrade path is:

1. install the updated package
2. create a fresh local workspace with `hephaes init`
3. re-register local asset paths

## Desired User Experience

### Create a workspace in the current directory

After `pip install hephaes`, the user chooses a working directory and initializes the workspace there:

```bash
mkdir my-data-project
cd my-data-project
hephaes init
```

That creates:

```text
./.hephaes/
```

### Register assets by path

The user adds assets by path:

```bash
hephaes add ~/Downloads/demo/optimal_0.mcap
```

The asset is not copied.

Instead, the workspace database stores the normalized absolute path, and that path becomes the canonical source used by package workflows.

### Use the asset for everything else

After registration, the package uses the stored path for:

- indexing
- inspection
- draft creation
- preview
- confirmation
- conversion

Generated artifacts still live in the local workspace.
Only the original source asset remains outside it.

## Design Principles

### Linked assets only

`hephaes` should support exactly one local asset model:

- the workspace records a path to the original file
- package operations open that file directly

There should be no asset-copy mode and no "upload into workspace storage" concept.

### Local workspaces stay local

Workspaces should continue to be local `.hephaes/` directories rooted at the user's chosen project or working directory.

The package should continue to support:

- `hephaes init` in the current directory
- `hephaes init /path/to/root`
- upward workspace discovery from the current working directory
- `--workspace` as an explicit filesystem path

This change should not introduce a home-directory workspace manager or named workspace registry.

### `Workspace` remains the durable package boundary

The durable package entry point remains `Workspace`.

`Workspace` should own:

- workspace resolution
- asset registration
- draft/config persistence
- conversion run persistence

The CLI should stay a thin adapter over that package boundary.

### Generated state belongs in the workspace

The workspace should own generated and durable package state such as:

- SQLite database
- saved spec documents
- draft revision documents
- jobs
- outputs

The workspace should not own copies of raw input assets.

## Filesystem Layout

Suggested local layout:

```text
<project-root>/
  .hephaes/
    workspace.sqlite3
    outputs/
    specs/
      revisions/
      drafts/
    jobs/
```

Notes:

- the workspace root stays local to the project or chosen directory
- there is no `imports/` directory

## Workspace Resolution Model

### Local initialization

The package should continue to treat the workspace root as a filesystem root chosen by the user.

Examples:

```bash
hephaes init
hephaes init /path/to/project-root
```

`Workspace.init(".")` should continue to create:

```text
./.hephaes
```

### Upward discovery stays

The package can continue to discover the current workspace by walking upward from the current directory until it finds `.hephaes/`.

That means:

- `Workspace.open()` still works naturally from inside a project tree
- `--workspace` remains an override when the user wants an explicit root

## Asset Model

### Canonical asset path

The asset row should store one canonical absolute path.

That path should be:

- expanded from `~`
- resolved to an absolute path
- used as the runtime path for all package operations

### Simplified asset record

The asset schema should be simplified around linked files.

At minimum, assets should retain:

- `id`
- `file_path`
- `file_name`
- `file_type`
- `file_size`
- `indexing_status`
- `last_indexed_at`
- `registered_at`
- `updated_at`

The package should no longer model:

- `source_path`
- `imported_at`
- copy destinations inside the workspace

### Missing-path behavior

Because assets are linked by path, the package must treat path availability as a first-class runtime concern.

If a registered file has been moved or deleted, package operations should fail with a clear workspace-level error instead of surfacing a generic reader failure.

## Package Behavior By Area

### Asset registration

Registering an asset should:

1. validate the path and file type
2. normalize it to a canonical absolute path
3. record the asset in the workspace database
4. not copy any bytes into the workspace

### Indexing

Indexing should open the registered `file_path` directly.

Refreshing an asset should refresh recorded metadata from the original path, not re-copy the asset.

### Inspection and authoring

Inspection, draft creation, preview, and conversion should all resolve the asset id to the stored `file_path` and operate from there.

### Conversion outputs

Conversion outputs should continue to be written into the workspace output area.

Run and output records should still preserve lineage back to:

- the workspace asset id
- the source asset path
- the saved config id when applicable

## CLI Surface

### Workspace commands

The workspace CLI remains path-oriented rather than name-oriented.

Recommended commands:

- `hephaes init`
- `hephaes init /path/to/root`

### Workspace option semantics

`--workspace` should continue to accept a filesystem path:

```bash
hephaes ls assets --workspace /path/to/project-root
hephaes drafts wizard --workspace /path/to/project-root <asset-id>
```

When `--workspace` is omitted, commands can continue to rely on upward `.hephaes` discovery from the current working directory.

### Asset command wording

The CLI and docs should stop using language that implies file copying.

Preferred language:

- register asset
- link asset
- source path

Avoid:

- upload asset
- import into workspace storage
- copied asset

## Internal Package Shape

### Workspace management stays simple

The package does not need a separate home-directory workspace-management layer.

Most workspace-opening behavior can stay close to the current implementation:

- local `.hephaes` directories
- path-based init/open
- upward discovery

### Asset registration logic

`workspace/assets.py` should be simplified to path registration and path lookup.

File-copy helpers and import-destination builders should be removed from the asset registration path.

### Existing authoring and conversion logic

Most authoring and conversion logic can remain structurally the same because those flows already resolve `asset.file_path`.

The main change is that `file_path` becomes the original source path instead of a copied workspace path.

## Tradeoffs

### Benefits

- no duplicated raw logs
- less disk usage
- simpler mental model
- conversion jobs always use the canonical source path
- easier to point the package at large existing local datasets

### Costs

- moving or deleting a registered file breaks later operations
- workspaces are less self-contained because they do not contain raw inputs

This tradeoff is acceptable because the package is explicitly local-first and path-based.

## Out Of Scope For This Change

This redesign should not expand into:

- home-directory workspace registries
- active workspace selection outside the current local workspace model
- remote asset storage
- background sync of moved asset paths
- mixed local and remote source abstractions

The goal is a smaller, cleaner local package model, not a broader workspace-management system.
