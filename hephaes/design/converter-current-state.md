# Conversion Current State

## Snapshot

`hephaes` already covers a large part of the conversion and authoring workflow.

The library currently supports:

- reading ROS1 and ROS2 logs
- legacy mapping conversion
- trigger-based schema-aware conversion
- explicit `row_strategy` spec modeling with trigger compatibility through `assembly`
- feature-source unions for `path`, `constant`, `metadata`, `concat`, and `stack`
- draft-origin metadata on inferred specs
- declarative transforms for images, numeric values, and sequences
- spec serialization and migration helpers for the richer v2 contract shape
- capability metadata that distinguishes authoring surface from current runtime support
- introspection, draft-spec generation, and preview helpers
- validation, sharding, manifests, and conversion reports

The code has been exercised with the hephaes test suite and the current authoring-focused tests are passing (`278 passed`).

## Implemented In `hephaes`

### Conversion contract and serialization

- `hephaes/src/hephaes/models.py` now contains the normalized `ConversionSpec` shape, including `row_strategy`, source-expression variants, and `draft_origin` metadata while keeping `assembly`, `mapping`, and legacy resample compatibility.
- `hephaes/src/hephaes/conversion/spec_io.py` provides JSON/YAML serialization and migration helpers that normalize older payloads into the current richer shape.
- `hephaes/src/hephaes/conversion/capabilities.py` publishes both authoring-level surface area and the narrower set of runtime-supported row strategies and source kinds.

### Authoring core

- `hephaes/src/hephaes/conversion/introspection.py` samples decoded payloads and infers field candidates.
- `hephaes/src/hephaes/conversion/draft_spec.py` turns inspection results into editable `ConversionSpec` drafts and now carries draft provenance into `draft_origin`.
- `hephaes/src/hephaes/conversion/preview.py` previews trigger-based assembled rows and extracted feature values.

### Runtime conversion

- `hephaes/src/hephaes/conversion/assembly.py` assembles trigger records.
- `hephaes/src/hephaes/conversion/features.py` resolves feature sources and applies transform chains.
- `hephaes/src/hephaes/conversion/validation.py` validates sampled trigger records before writing.
- `hephaes/src/hephaes/converter.py` executes legacy mapping and schema-aware trigger flows.

### Output and reporting

- `hephaes/src/hephaes/conversion/layout.py` handles sharding and split layout.
- `hephaes/src/hephaes/conversion/report.py` writes conversion reports.
- `hephaes/src/hephaes/outputs/` contains the TFRecord and Parquet writers used by the converter.

## What Is Still Partial

The biggest product gaps are still around authoring flexibility and cross-package integration.

- schema-aware conversion is still effectively trigger-centric at runtime even though `row_strategy` is now modeled explicitly
- richer feature-source variants are represented in the spec, but runtime evaluation is still path-only
- backend and frontend contracts for reusable configs, inspections, drafts, and previews are still only planned
- the config-first demo and reusable-config UX still need a final pass to reflect the intended authoring flow

## Current Limitations To Keep In Mind

- If a user does not provide a schema-aware spec, the converter still falls back to the legacy mapping path.
- `per-message` and `resample` row strategies are modeled in the spec but are not yet executable through the shared conversion runtime.
- `constant`, `metadata`, `concat`, and `stack` sources serialize and validate today, but conversion/preview runtime paths still raise explicit unsupported errors for them.
- The authoring helpers are useful, but they are heuristic by nature and should be treated as draft generation rather than a guaranteed final contract.
- The business-logic package is ready for reuse, but backend/frontend wiring is still a future step.

## Where To Look Next

- Master plan: [`converter-design.md`](./converter-design.md)
- Remaining work: [`converter-implementation.md`](./converter-implementation.md)
