# CLI-First Authoring Implementation Plan

## Objective

Implement the full package-owned conversion authoring workflow in `hephaes` so that a user can go from source asset to saved conversion config entirely through the package CLI.

This implementation plan is intentionally package-first:

- `hephaes` owns the workflow rules
- `Workspace` owns the durable state transitions
- the CLI is the required human interface
- future backends reuse package methods instead of recreating business logic

## Delivery Rules

- Complete phases in order unless a later phase explicitly depends only on stable public interfaces.
- Do not put HTTP-shaped or frontend-shaped models into the package.
- Keep pure authoring logic in `hephaes.conversion`.
- Keep durable workflow orchestration in `hephaes.workspace`.
- Treat the interactive wizard as a required deliverable, not a nice-to-have.

## Progress Tracking

| Phase | Status | Notes |
| --- | --- | --- |
| 1 | completed | Added draft-head models, `conversion_drafts` schema, legacy migration, and compatible draft-head writes from the existing draft revision path. |
| 2 | completed | Refactored `workspace/drafts.py` around draft heads plus revisions, added public draft lookup APIs and draft lifecycle errors, and expanded workspace/package export coverage. |
| 3 | completed | Added package-owned `Workspace` authoring methods for inspect/create/update/preview/confirm/discard plus reader error normalization and workflow tests. |
| 4 | completed | Added a scriptable `drafts` command group covering create/ls/show/update/preview/confirm/discard/save-config on top of `Workspace`. |
| 5 | not started | Pending required interactive wizard. |
| 6 | completed | Pulled forward to unblock the CLI save flow; added `Workspace.save_conversion_config_from_draft(...)`, draft-to-config lineage in config metadata, and promotion coverage including conversion execution. |
| 7 | not started | Pending expanded workflow and migration validation. |
| 8 | not started | Pending final docs/examples refresh. |

## Phase Summary

| Phase | Outcome |
| --- | --- |
| 1 | Drafts become first-class durable entities |
| 2 | Workspace gets stable draft/config persistence primitives |
| 3 | Workspace owns inspect/draft/update/preview/confirm/discard workflow methods |
| 4 | Scriptable CLI commands cover the full lifecycle |
| 5 | Interactive wizard becomes the default human workflow |
| 6 | Saved config promotion and conversion lineage are fully wired |
| 7 | Tests cover migrations, workflow behavior, and CLI flows |
| 8 | Docs and examples reflect the new package-owned workflow |

## Phase 1: Draft Domain Model And Schema

### Goal

Introduce a proper draft head model so a draft is no longer represented only by revision rows.

### Status

Completed on `2026-03-28`.

### Tasks

- Add draft-head models to `workspace/models.py`:
  - `ConversionDraftSummary`
  - `ConversionDraft`
- Keep `ConversionDraftRevisionSummary` and `ConversionDraftRevision`, but narrow their responsibility to immutable revision history.
- Define canonical draft status values:
  - `draft`
  - `confirmed`
  - `saved`
  - `discarded`
- Add serialization helpers for draft heads in `workspace/serialization.py`.
- Update `workspace/schema.py` to create a new `conversion_drafts` table with:
  - `id`
  - `source_asset_id`
  - `status`
  - `current_revision_id`
  - `confirmed_revision_id`
  - `saved_config_id`
  - `created_at`
  - `updated_at`
  - `discarded_at`
- Update `conversion_draft_revisions` to include:
  - `draft_id`
  - `preview_request_json`
- Add indexes for:
  - `conversion_drafts.source_asset_id`
  - `conversion_drafts.saved_config_id`
  - `conversion_draft_revisions.draft_id`
- Write a forward migration for legacy workspaces:
  - create one draft head per existing legacy draft revision row
  - attach the existing row as revision `1`
  - carry forward `source_asset_id`
  - carry forward `saved_config_id`
  - map legacy status into the new draft head status
  - set `current_revision_id` to the migrated revision

### Dependencies

- None. This is the foundation for every later phase.

### Exit Criteria

- a draft can exist independently of its revisions
- legacy draft data opens successfully after migration
- new workspaces create both draft heads and draft revisions

## Phase 2: Workspace Persistence Primitives

### Goal

Add the low-level query and mutation primitives needed to manage drafts and draft revisions cleanly.

### Status

Completed on `2026-03-28`.

### Tasks

- Refactor `workspace/drafts.py` around draft heads plus revisions.
- Replace `record_conversion_draft_revision(...)` with clearer internal primitives such as:
  - `_create_conversion_draft(...)`
  - `_append_conversion_draft_revision(...)`
  - `_get_conversion_draft_summary_or_raise(...)`
  - `_set_conversion_draft_status(...)`
  - `_set_conversion_draft_current_revision(...)`
  - `_set_conversion_draft_confirmed_revision(...)`
  - `_set_conversion_draft_saved_config(...)`
- Add public lookup helpers:
  - `list_conversion_drafts(...)`
  - `get_conversion_draft(...)`
  - `resolve_conversion_draft(...)`
  - `list_conversion_draft_revisions(...)`
  - `get_conversion_draft_revision(...)`
- Add useful filters for draft listings:
  - by source asset
  - by status
  - by saved config
- Preserve spec migration-on-load behavior for draft revision documents.
- Add or refine workspace errors for:
  - draft not found
  - invalid draft state transition
  - draft confirmation requirements not met

### Dependencies

- Requires Phase 1 schema and model changes.

### Exit Criteria

- `Workspace` can create, load, update, and transition draft entities without any CLI or backend code
- draft revision history is queryable independently of workflow orchestration

## Phase 3: Package-Owned Authoring Workflow Methods

### Goal

Move the actual authoring workflow into `Workspace` so adapters only invoke package services.

### Status

Completed on `2026-03-28`.

### Tasks

- Add an internal reader helper in the workspace layer that:
  - resolves asset selectors
  - opens `RosReader`
  - normalizes reader/opening failures into package errors
- Implement `Workspace.inspect_asset(...)`:
  - accept asset selector plus optional `InspectionRequest`
  - open the reader internally
  - return `InspectionResult`
  - do not persist by default
- Implement `Workspace.create_conversion_draft(...)`:
  - run inspection
  - build an initial draft spec
  - create the draft head
  - append revision `1`
  - return the resolved draft
- Implement `Workspace.update_conversion_draft(...)`:
  - accept a full spec document or equivalent edit input
  - append a new immutable revision
  - update `current_revision_id`
  - clear or invalidate confirmation if the confirmed revision is no longer current
- Implement `Workspace.preview_conversion_draft(...)`:
  - preview the current revision unless a revision selector is provided
  - persist `preview_request_json`
  - persist `preview_json`
  - return the updated draft
- Implement `Workspace.confirm_conversion_draft(...)`:
  - require a successful preview on the target revision
  - set `confirmed_revision_id`
  - move status to `confirmed`
- Implement `Workspace.discard_conversion_draft(...)`:
  - move status to `discarded`
  - preserve existing revision history
- Ensure these methods are the only package-owned place that:
  - calls `inspect_reader`
  - calls `build_draft_conversion_spec`
  - calls `preview_conversion_spec`
  - enforces authoring lifecycle rules

### Dependencies

- Requires Phase 2 persistence primitives.

### Exit Criteria

- the full inspect -> draft -> preview -> confirm lifecycle can be executed directly through `Workspace`
- no external adapter is required to orchestrate authoring

## Phase 4: Scriptable CLI Command Surface

### Goal

Expose the package workflow through scriptable, non-interactive CLI commands.

### Status

Completed on `2026-03-28`.

### Tasks

- Add a new `cli/commands/drafts.py` module.
- Register the `drafts` command group in `cli/parser.py`.
- Implement scriptable commands:
  - `drafts create`
  - `drafts ls`
  - `drafts show`
  - `drafts update`
  - `drafts preview`
  - `drafts confirm`
  - `drafts discard`
  - `drafts save-config`
- Decide which commands support JSON output and implement it consistently:
  - `drafts create`
  - `drafts show`
  - `drafts preview`
  - `drafts save-config`
- Add `--yes` support where destructive or confirmation-sensitive:
  - `drafts confirm`
  - `drafts discard`
- Keep `inspect` for standalone inspection use cases.
- Keep `configs` for direct config CRUD, but document draft-first authoring as the primary path.

### Dependencies

- Requires Phase 3 workflow methods.

### Exit Criteria

- every workflow step is reachable from a non-interactive CLI command
- scripting and automation do not require private package APIs

## Phase 5: Required Interactive Wizard

### Goal

Ship a required interactive wizard that becomes the default human path through the authoring workflow.

### Tasks

- Implement `drafts wizard` in `cli/commands/drafts.py`.
- Support required entrypoints:
  - `hephaes drafts wizard <asset-id>`
  - `hephaes drafts wizard --draft <draft-id>`
- Design the wizard flow around real package state:
  - source asset selection or resume
  - inspection option review
  - draft generation
  - spec review
  - preview
  - confirmation
  - saved config naming
  - save
- Ensure the wizard persists normal drafts and configs through `Workspace`.
- Do not introduce hidden wizard-only persistence.
- Add clear step transitions:
  - continue
  - go back
  - cancel
  - discard draft
- Decide how the wizard handles edits between draft and preview:
  - either inline field/spec edits
  - or handoff to `drafts update`
- Print concise summaries after major steps:
  - draft id
  - selected topics
  - preview health
  - confirmation state
  - saved config id/name
- Ensure the wizard can resume a previously created draft without data loss.

### Dependencies

- Requires Phase 4 commands and Phase 3 workflow methods.

### Exit Criteria

- a user can complete the full workflow through the wizard alone
- the wizard is resume-capable
- the wizard is a thin CLI adapter over durable package state

## Phase 6: Draft Promotion, Saved Config Lineage, And Conversion Integration

### Goal

Make saving from a confirmed draft explicit and preserve the lineage needed for later conversions and queries.

### Status

Completed on `2026-03-28`.

### Tasks

- Add `Workspace.save_conversion_config_from_draft(...)`.
- Restrict promotion so it only works from a confirmed draft.
- Create the saved config from the confirmed revision document.
- Record lineage from saved config back to draft confirmation:
  - draft id
  - confirmed revision id
  - source asset id
- Update config persistence/query logic so saved configs can surface:
  - origin draft
  - confirmed revision
  - latest preview if applicable
- Decide where lineage lives:
  - config metadata
  - dedicated columns
  - revision description
  - or a combination
- Ensure `Workspace.run_conversion(...)` can continue to execute from saved configs created through draft promotion.
- Verify conversion run records preserve the saved config reference cleanly.

### Dependencies

- Requires Phase 3 confirmed drafts and Phase 2 stable config/draft persistence.

### Exit Criteria

- saving a config from a draft is a first-class package action
- saved config lineage is durable and queryable
- conversions can run from promoted configs without adapter-side glue

## Phase 7: Tests And Migration Validation

### Goal

Lock in the workflow behavior and reduce migration risk.

### Tasks

- Add package tests for draft head creation.
- Add package tests for draft revision append/update behavior.
- Add package tests for preview persistence on revisions.
- Add package tests for confirmation requirements.
- Add package tests for discard behavior.
- Add package tests for save-config-from-draft behavior.
- Add package tests for draft-to-config lineage queries.
- Add migration tests for legacy draft rows opening under the new schema.
- Add CLI tests for scriptable commands:
  - `drafts create`
  - `drafts preview`
  - `drafts confirm`
  - `drafts discard`
  - `drafts save-config`
- Add wizard tests for:
  - happy path from asset to saved config
  - resume existing draft
  - cancel before save
  - discard from inside the wizard
  - reject confirmation without successful preview
  - reject save without confirmation
- Add an end-to-end flow test:
  1. register asset
  2. create draft
  3. preview draft
  4. confirm draft
  5. save config from draft
  6. run conversion from saved config
  7. assert lineage and output records

### Dependencies

- Requires Phases 1 through 6.

### Exit Criteria

- authoring behavior is covered at package and CLI levels
- migration behavior is verified
- the end-to-end draft-to-config-to-convert flow is tested

## Phase 8: Documentation And Examples

### Goal

Make the new workflow understandable and discoverable for package users.

### Tasks

- Update `README.md` with the new CLI-first authoring workflow.
- Add examples for:
  - draft creation
  - draft preview
  - draft confirmation
  - save-config-from-draft
  - wizard flow
- Document the difference between:
  - pure stateless helpers in `hephaes.conversion`
  - durable workflow methods on `Workspace`
  - CLI adapters over `Workspace`
- Add migration notes if old draft records are being upgraded automatically.
- Document the recommended user path:
  - wizard for humans
  - scriptable commands for automation

### Dependencies

- Requires the user-facing CLI surface from Phases 4 and 5.

### Exit Criteria

- users can discover and run the full authoring workflow from package docs alone

## Recommended Delivery Order

The recommended merge order is:

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 6
5. Phase 4
6. Phase 5
7. Phase 7
8. Phase 8

This keeps the core durable and package-owned behavior stable before building the required wizard.

## Key Decisions

### Confirmation stays explicit

Preview is evidence. Confirmation is a separate user action.

### Save requires confirmation

Do not allow unconfirmed drafts to silently become saved configs.

### Wizard uses real package state

The wizard must not own hidden state or alternate workflow rules.

### Package stays adapter-neutral

Package methods return package models. Adapters may reshape them later, but they do not own the underlying workflow.

## Deliverable Summary

When this plan is complete, `hephaes` will support:

- package-owned inspection
- package-owned draft creation and revision history
- package-owned preview and confirmation
- package-owned promotion from draft to saved config
- a required interactive CLI wizard for the entire authoring lifecycle
- scriptable CLI commands for the same lifecycle
- saved config lineage back to draft confirmation
- future adapter reuse without duplicated business logic
