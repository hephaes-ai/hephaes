# Conversion Implementation Tasks

## Purpose

This document is the phased implementation backlog for the remaining conversion work.

It is derived from:

- the product direction in [`converter-design.md`](./converter-design.md)
- the actual implementation snapshot in [`converter-current-state.md`](./converter-current-state.md)

This is intentionally more execution-oriented than the master plan. It focuses on what still needs to be built, in what order, and how we will know each phase is actually done.

## Planning Assumptions

The current baseline already gives us:

- `ConversionSpec`, spec serialization, and migration helpers
- explicit `row_strategy` and source-expression spec models
- draft-origin metadata for inferred specs
- capability metadata that distinguishes authoring surfaces from current runtime support
- trigger-based schema-aware conversion
- introspection, draft-spec generation, and preview helpers
- validation, sharding, manifests, and reports

The main gaps are:

- the config-first demo and reusable-config workflow are still incomplete
- backend and frontend contract wiring still needs to be built around the `hephaes` business-logic surface

## Phase 1: Normalize The Spec Model Around The Missing Runtime Concepts

Status: complete

Goal:
Turn the current spec into the final contract shape we actually need, without breaking existing callers.

### Tasks

- Add an explicit row-strategy model instead of using `assembly` as the only schema-aware entrypoint.
- Define a feature-source union that can represent `path`, `constant`, `metadata`, `concat`, and `stack`.
- Add draft-origin metadata so inferred specs can carry assumptions, warnings, and provenance into preview and reporting.
- Keep `mapping`, `resample`, `output`, and `write_manifest` compatibility paths working through `ConversionSpec.from_legacy()`.
- Extend capability metadata so it advertises only what the runtime actually supports at each step.
- Extend spec I/O and migration helpers for the richer row-strategy and feature-source payloads.

### Likely Files

- `hephaes/src/hephaes/models.py`
- `hephaes/src/hephaes/conversion/spec_io.py`
- `hephaes/src/hephaes/conversion/capabilities.py`
- `hephaes/src/hephaes/__init__.py`

### Testing / Debug

- Add model-validation tests for each new row-strategy and feature-source variant.
- Add migration tests from the current document format into the richer spec format.
- Add legacy-translation tests proving old inputs still load into the new spec shape.

### Exit Criteria

- A saved spec can describe the row layout and feature sources without custom Python.
- Existing legacy callers still load and run.

### Completed

- Added explicit `row_strategy` support for `trigger`, `per-message`, and `resample` while preserving `assembly` compatibility for trigger-based specs.
- Added source-expression models for `path`, `constant`, `metadata`, `concat`, and `stack`.
- Added `draft_origin` metadata so inferred specs carry provenance, assumptions, and warnings.
- Bumped spec document handling to the richer normalized shape and added migration coverage for row strategy and source kind normalization.
- Split capability metadata into authoring-vs-runtime support so downstream clients can avoid assuming unimplemented runtime paths.
- Added runtime guards so non-path source expressions fail explicitly instead of silently misbehaving before phase 3 lands.

## Phase 2: Build A Shared Row-Construction Engine

Status: complete

Goal:
Make row construction a first-class stage that preview, validation, and final conversion all share.

### Tasks

- Refactor trigger assembly into a row-construction layer with strategy implementations for `trigger`, `per-message`, and `resample`.
- Keep trigger joins for `nearest`, `last-known-before`, and `exact-within-tolerance`.
- Support tolerance, staleness, required/optional handling, and missing-data policy at the row-construction level.
- Route `Converter.convert()` through the row-strategy layer so schema-aware conversion does not silently depend on legacy mapping fallback.
- Update preview and validation to consume row-construction output instead of duplicating partial assembly logic.
- Keep deterministic ordering guarantees across all row strategies.

### Likely Files

- `hephaes/src/hephaes/conversion/assembly.py`
- `hephaes/src/hephaes/converter.py`
- `hephaes/src/hephaes/conversion/preview.py`
- `hephaes/src/hephaes/conversion/validation.py`

### Testing / Debug

- Add timeline fixtures that exercise all row strategies.
- Add sync-policy tests for exact match, nearest match, stale joins, and required-join failures.
- Add repeated-run tests to confirm row order and presence flags are stable.

### Exit Criteria

- A schema-aware spec can build rows without being trigger-only.
- Preview, validation, and conversion all operate on the same row model.

### Completed

- Added a shared row-construction entrypoint that dispatches by `row_strategy`.
- Kept the trigger assembly API intact as a compatibility wrapper on top of the shared layer.
- Added executable row construction for `trigger`, `per-message`, and `resample` strategies.
- Routed preview, validation, and schema-aware conversion through the same constructed-row model.
- Added regression coverage for per-message rows, resample interpolation preview, and converter execution on the per-message path.

## Phase 3: Implement Source-Expression Evaluation

Status: complete

Goal:
Remove the need for custom Python builder functions by letting features be composed declaratively.

### Tasks

- Replace the current path-only runtime guard with real source-expression evaluation.
- Implement evaluators for `path`, `constant`, `metadata`, `concat`, and `stack`.
- Allow features and labels to consume the richer source-expression model.
- Keep existing path-based features working as the simplest source-expression case.
- Ensure transform application and shape validation happen after source resolution, not before.
- Define how missing values propagate through composed sources.

### Likely Files

- `hephaes/src/hephaes/models.py`
- `hephaes/src/hephaes/conversion/features.py`
- `hephaes/src/hephaes/conversion/draft_spec.py`
- `hephaes/src/hephaes/conversion/validation.py`

### Testing / Debug

- Add unit tests for each source kind.
- Add composition tests for mixed numeric and sequence payloads.
- Add negative tests for invalid concatenation, incompatible shapes, and missing metadata.

### Exit Criteria

- A user can define Doom-compatible and non-Doom-compatible contracts without writing a custom builder function.
- Feature extraction works for both simple path sources and composed sources.

### Completed

- Replaced the phase-1 path-only runtime guard with real source-expression evaluation.
- Added runtime evaluators for `path`, `constant`, `metadata`, `concat`, and `stack`.
- Shifted feature extraction to evaluate against full row context so metadata and multi-topic composition work at runtime.
- Updated preview, validation, and schema-aware conversion to use the shared source-expression evaluator.
- Added regression coverage for feature-builder composition and end-to-end converter execution with declarative composed sources.

## Phase 4: Tighten Preflight Validation And Authoring Preview

Status: complete

Goal:
Make preview and validation the reliable gate before long-running conversion.

### Tasks

- Add a preflight mode that resolves inputs, builds sample rows, validates features, and stops before shard writing.
- Add explicit schema compatibility checks for dtype, shape, required features, and label contract.
- Add richer preview output for assembled rows, extracted feature values, presence behavior, and missing-data behavior.
- Add missing-topic and missing-feature rate summaries to preview and validation results.
- Add label summaries where label configuration is present.
- Keep fail-fast and bad-record-budget behavior aligned between preflight and full conversion.

### Likely Files

- `hephaes/src/hephaes/conversion/preview.py`
- `hephaes/src/hephaes/conversion/validation.py`
- `hephaes/src/hephaes/converter.py`

### Testing / Debug

- Add preflight-only tests that confirm no shards are written on failure.
- Add failure-path tests for invalid shapes, invalid dtypes, and required-feature mismatches.
- Add preview regression tests that verify warnings and missing-data summaries.

### Exit Criteria

- Preview is useful as an authoring review step, not just a thin sample dump.
- Preflight catches contract problems before the write path begins.

### Completed

- Added `preflight_conversion_spec()` as a shared authoring gate that resolves rows, validates features, and returns before shard writing.
- Added explicit dtype validation alongside the existing shape and required-feature checks.
- Added label-contract validation and label summary reporting to preflight/preview output.
- Added missing-topic and missing-feature counts plus rates to the preview/preflight surface.
- Kept fail-fast and bad-record-budget behavior aligned by reusing the same validation path in preview/preflight and full conversion.

## Phase 5: Align Reporting And Runtime Metadata With The Richer Contract

Status: complete

Goal:
Make manifests and reports reflect the actual authored contract and conversion path.

### Tasks

- Add row-strategy metadata to manifests and reports.
- Add richer source-definition metadata for features and labels.
- Add draft-origin metadata when a run starts from an inferred draft.
- Add preview summary metadata where preview or preflight is used.
- Keep split counts, shard naming, and validation summaries aligned with the richer runtime contract.
- Make sure report content stays deterministic across reruns.

### Likely Files

- `hephaes/src/hephaes/conversion/report.py`
- `hephaes/src/hephaes/manifest.py`
- `hephaes/src/hephaes/converter.py`

### Testing / Debug

- Add manifest snapshot tests for schema, row strategy, and draft-origin fields.
- Add regression tests for deterministic shard naming and split assignment.
- Re-run the same fixture twice and compare output metadata.

### Exit Criteria

- A conversion artifact tells the full story of how rows were constructed and features were produced.

### Completed

- Added row-strategy metadata to schema-aware manifests and reports.
- Added richer feature and label config metadata, including composed-source definitions.
- Added draft-origin metadata to conversion artifacts when a run starts from an inferred draft.
- Added preflight summary metadata so reports capture the validation gate that ran before writing.
- Kept missing-feature and missing-topic summaries aligned with the runtime validation path.

## Phase 6: Rewrite The Authoring Demo Around The Real Workflow

Status: partial

Goal:
Make the demo and docs teach inspect -> draft -> edit -> preview -> convert instead of preset-first usage.

### Tasks

- Rewrite `hephaes/demo/core_demo.ipynb` around the config-first authoring loop.
- Keep Doom as one worked example of editing a generic draft into a concrete contract.
- Show how to override a draft declaratively without defining a custom Python function.
- Add examples for saving, loading, and migrating spec documents with the public library entrypoints.

### Likely Files

- `hephaes/demo/core_demo.ipynb`
- `hephaes/design/converter-design.md`
- `hephaes/design/converter-current-state.md`

### Testing / Debug

- Add one smoke test or notebook-adjacent scripted check that runs the documented authoring flow.
- Verify the demo still works with the current public API after each spec-model change.

### Exit Criteria

- The recommended usage pattern is clearly config-first.
- A new teammate could follow the demo without discovering an old preset-first mental model.

## Phase 7: Add Backend Authoring And Reusable-Config Contracts

Status: not started

Goal:
Let backend APIs expose inspection, drafting, preview, and reusable-config persistence without rebuilding converter semantics.

### Tasks

- Define backend request and response schemas for inspection, draft generation, preview, capabilities, saved configs, and draft revisions.
- Add backend endpoints and services that call `hephaes` entrypoints for inspection, draft, preview, validation, serialization, and migration.
- Add persistence for reusable configs, draft revisions, and starter templates.
- Keep legacy conversion requests working by translating them into the richer spec model where possible.
- Align backend validation errors with `hephaes` validation language so the contract feels consistent.

### Cross-Reference

- `backend/design/conversion-authoring-and-reusable-configs.md`

### Testing / Debug

- Add API tests for legacy and new payloads.
- Add persistence tests for saved-config create, load, update, duplicate, and migration.
- Trace one end-to-end request from API payload to `Converter` invocation.

### Exit Criteria

- The backend can create, preview, save, reopen, and execute reusable conversion configs through library-backed logic.

## Phase 8: Add Frontend Authoring Flows On Top Of The Backend Contract

Status: not started

Goal:
Expose the reusable-config authoring workflow in the UI without hard-coding converter semantics in TypeScript.

### Tasks

- Add typed frontend API helpers for capabilities, inspection, draft generation, preview, saved configs, and execution.
- Build the conversion route around authoring states: inspect, draft, edit, preview, save, and submit.
- Add saved-config browsing, reopening, duplicate, rename, and update flows.
- Keep frontend validation focused on UX-only checks while semantic validation stays backend and `hephaes` backed.
- Surface capability-driven forms so row strategies, source kinds, transforms, and dtypes are not hard-coded in frontend code.

### Cross-Reference

- `frontend/design/conversion-authoring-and-reusable-configs.md`

### Testing / Debug

- Add contract tests for typed API consumption.
- Add workflow tests for preview-before-submit and saved-config reuse.
- Verify the UI can reopen an older saved config and show any migration messaging from the backend.

### Exit Criteria

- A user can author and reuse configs through the frontend without writing Python or editing raw JSON by hand.

## Suggested Delivery Order

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4
5. Phase 5
6. Phase 6
7. Phase 7
8. Phase 8

This order keeps the library contract ahead of backend/frontend adoption and reduces the risk of shipping API shapes that have to be redesigned once the runtime becomes truly generic.
