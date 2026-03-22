# Conversion Current State

## Snapshot

`hephaes` already covers a large part of the conversion and authoring workflow.

The library currently supports:

- reading ROS1 and ROS2 logs
- legacy mapping conversion
- schema-aware conversion with shared `trigger`, `per-message`, and `resample` row construction
- explicit `row_strategy` spec modeling with trigger compatibility through `assembly`
- feature-source unions for `path`, `constant`, `metadata`, `concat`, and `stack`
- runtime source-expression evaluation for `path`, `constant`, `metadata`, `concat`, and `stack`
- draft-origin metadata on inferred specs
- preflight and preview summaries with missing-data rates and label validation
- manifests and reports that carry row strategy, composed source metadata, draft provenance, and preflight summaries
- declarative transforms for images, numeric values, and sequences
- spec serialization and migration helpers for the richer v2 contract shape
- capability metadata that distinguishes authoring surface from current runtime support
- introspection, draft-spec generation, and preview helpers
- validation, sharding, manifests, and conversion reports

The code has been exercised with the hephaes test suite and the current authoring-focused tests are passing (`287 passed`).

## Implemented In `hephaes`

### Conversion contract and serialization

- `hephaes/src/hephaes/models.py` now contains the normalized `ConversionSpec` shape, including `row_strategy`, source-expression variants, and `draft_origin` metadata while keeping `assembly`, `mapping`, and legacy resample compatibility.
- `hephaes/src/hephaes/conversion/spec_io.py` provides JSON/YAML serialization and migration helpers that normalize older payloads into the current richer shape.
- `hephaes/src/hephaes/conversion/capabilities.py` publishes both authoring-level surface area and the narrower set of runtime-supported row strategies and source kinds.

### Authoring core

- `hephaes/src/hephaes/conversion/introspection.py` samples decoded payloads and infers field candidates.
- `hephaes/src/hephaes/conversion/draft_spec.py` turns inspection results into editable `ConversionSpec` drafts and now carries draft provenance into `draft_origin`.
- `hephaes/src/hephaes/conversion/preview.py` previews rows through the shared row-construction layer, exposes preflight summaries, and reports missing-data and label information.

### Runtime conversion

- `hephaes/src/hephaes/conversion/assembly.py` now owns the shared row-construction layer for trigger, per-message, and resample strategies.
- `hephaes/src/hephaes/conversion/features.py` resolves source expressions, applies transform chains, and evaluates row metadata.
- `hephaes/src/hephaes/conversion/validation.py` validates sampled constructed rows before writing, including dtype and label-contract checks.
- `hephaes/src/hephaes/converter.py` executes legacy mapping and schema-aware flows through the shared row-construction path.

### Output and reporting

- `hephaes/src/hephaes/conversion/layout.py` handles sharding and split layout.
- `hephaes/src/hephaes/conversion/report.py` writes conversion reports that include row strategy, label config, draft origin, and preflight summaries.
- `hephaes/src/hephaes/manifest.py` writes manifests that carry richer contract metadata for schema-aware runs.
- `hephaes/src/hephaes/outputs/` contains the TFRecord and Parquet writers used by the converter.

## What Is Still Partial

The biggest product gaps are still around authoring flexibility and cross-package integration.

- non-trigger row strategies exist, but advanced join semantics are still only defined for trigger-based assembly
- backend and frontend contracts for reusable configs, inspections, drafts, and previews are still only planned
- the config-first demo and reusable-config UX still need a final pass to reflect the intended authoring flow

## Current Limitations To Keep In Mind

- If a user does not provide a schema-aware spec, the converter still falls back to the legacy mapping path.
- trigger joins support richer sync and missing-data policies than the current `per-message` and `resample` strategies.
- manifest `mapping_resolved` still collapses composed sources down to a best-effort single-topic summary or `null`.
- preflight is currently surfaced as a library function and preview payload rather than a dedicated persisted backend/frontend workflow.
- The authoring helpers are useful, but they are heuristic by nature and should be treated as draft generation rather than a guaranteed final contract.
- The business-logic package is ready for reuse, but backend/frontend wiring is still a future step.

## Where To Look Next

- Master plan: [`converter-design.md`](./converter-design.md)
- Remaining work: [`converter-implementation.md`](./converter-implementation.md)
