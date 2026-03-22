# MCAP To TFRecord Conversion Implementation Plan

## Overview

This document turns the converter design into a concrete implementation plan for the current `hephaes` codebase.

The present implementation is already useful, but it still leaves the user with too much authoring work:

- `hephaes/src/hephaes/reader.py` reads raw or decoded messages.
- `hephaes/src/hephaes/converter.py` can execute either a legacy mapping flow or a schema-aware trigger flow.
- `hephaes/src/hephaes/conversion/transforms.py` already supports a meaningful declarative transform chain.
- `hephaes/demo/core_demo.ipynb` still teaches a preset-first workflow instead of a config-first workflow.
- there is no inspection or spec-drafting layer that helps a user turn an arbitrary MCAP into an editable training contract.

The real product goal is broader than a Doom preset:

- inspect any MCAP
- understand what fields and message shapes exist
- draft a conversion spec as data
- edit the draft without writing Python functions
- preview the resulting contract
- convert into the TFRecord layout a training setup expects

That means we need to finish two connected pieces:

1. a generic runtime conversion contract
2. an authoring layer that makes that contract discoverable and editable

The runtime path without the authoring layer is still too code-first for the intended use case.

Companion design doc:

- [`converter-introspection-and-draft-spec.md`](./converter-introspection-and-draft-spec.md)

## Implementation Strategy

The safest path is to keep the current runtime working while reshaping the user-facing workflow around declarative authoring.

That means:

- keep legacy `mapping`, `resample`, `output`, and `write_manifest` inputs working
- keep schema-aware conversion data-driven
- generalize the schema-aware path beyond trigger-only cases
- add inspection, draft-spec generation, and authoring preview as first-class stages
- treat built-in templates as optional examples, not the primary workflow

## Tasks

This is the execution checklist for the plan above. The detailed phase sections that follow provide the supporting rationale and implementation notes.

### Phase 1: Strengthen The Schema-Aware Config Model

- [ ] Add richer config models for input discovery, decoding, row construction, feature mapping, transforms, labels, splitting, output, and validation.
- [ ] Preserve the current `mapping`, `resample`, `output`, and `write_manifest` inputs as compatibility fields.
- [ ] Add JSON and YAML load-dump helpers so the main user-facing path can be config-first.
- [ ] Keep built-in templates available, but frame them as starter specs instead of required Python helpers.
- Testing / debug: add unit tests for config validation, legacy translation, and config serialization, then run a dry conversion and inspect the manifest for schema name and version fields.

### Phase 2: Split The Pipeline Into Explicit Runtime And Authoring Stages

- [ ] Keep `RosReader` focused on raw log access, topic iteration, and metadata extraction.
- [ ] Keep discovery and decoding as explicit runtime stages.
- [ ] Add explicit authoring stages for inspection, draft-spec generation, and preview.
- [ ] Keep writing and reporting downstream of validated feature payloads only.
- Testing / debug: add stage-level tests that compare requested topics, decoded payloads, inspected payload trees, and final feature outputs for the same fixture.

### Phase 3: Generalize Record Construction Beyond Trigger-Only Specs

- [ ] Support declarative row strategies such as `trigger`, `per-message`, and resampled timelines.
- [ ] Keep trigger joins for `nearest`, `last-known-before`, and `exact-within-tolerance`.
- [ ] Add per-topic tolerance, staleness limits, required flags, optional flags, and missing-data behavior.
- [ ] Ensure schema-aware conversion does not silently fall back to the legacy mapping path just because the user did not pick a trigger strategy.
- Testing / debug: build synthetic timeline tests for each row strategy and sync policy, then debug assembled rows by verifying timestamps, joined values, and presence flags.

### Phase 4: Generalize Feature Sources, Transforms, And Encoding

- [ ] Define explicit features with source expressions instead of only a single topic plus field path.
- [ ] Add source kinds such as `path`, `constant`, `metadata`, `concat`, and `stack`.
- [ ] Keep image transforms for channel conversion, resize, crop, normalization, and encoding format selection.
- [ ] Keep numeric transforms, sequence padding and truncation, label derivation, and class mapping support declarative.
- Testing / debug: add round-trip tests for PNG image bytes, vector assembly, numeric casts, source composition, and shape validation, then debug a Doom-shaped sample without using a custom Python builder.

### Phase 5: Add Validation, Preflight, And Authoring Preview

- [ ] Validate dtype and shape before writing any record.
- [ ] Add schema compatibility checks, sample-N preflight validation, and fail-fast handling for required feature mismatches.
- [ ] Add a bad-record budget, missing-topic rates, label summaries, and dry-run mode.
- [ ] Add preview support for assembled rows and extracted feature values before the full write path runs.
- Testing / debug: add failure-path tests for missing required features and invalid shapes, then run preflight-only mode and confirm it stops before shard writing when a contract is broken.

### Phase 6: Add Sharding, Splitting, And Deterministic Output

- [ ] Add shard counts, file naming templates, GZIP or uncompressed output, and deterministic ordering.
- [ ] Support train, val, and test splits with time-based or random strategies and a fixed seed.
- [ ] Keep shard and split outputs stable across reruns so results are easy to compare.
- Testing / debug: add tests that verify shard naming, split assignment stability, and repeated-run determinism, then rerun the same fixture twice and diff the emitted outputs.

### Phase 7: Update The Manifest And Conversion Report

- [ ] Add schema name and version.
- [ ] Add resolved feature definitions.
- [ ] Add per-feature missing rates.
- [ ] Add record counts and dropped counts.
- [ ] Add split counts.
- [ ] Add validation summary.
- [ ] Add row-strategy and draft-origin metadata where relevant.
- [ ] Keep the existing source metadata and temporal metadata.
- Testing / debug: add checks for manifest schema fields, summary counts, preview metadata, and draft-origin metadata, then verify the report matches the emitted shards.

### Phase 8: Update The Backend Conversion And Authoring Contract

- [ ] Extend `backend/app/schemas/conversions.py` to accept the richer converter config.
- [ ] Translate legacy backend requests into the new converter spec when possible.
- [ ] Add backend request and response shapes for inspection, draft-spec generation, and authoring preview.
- [ ] Align backend validation errors with library validation errors so the user sees one consistent contract.
- Testing / debug: add API tests for both legacy and new payload shapes, plus failure cases for invalid schema contracts and draft-spec requests, then trace one request from API payload to `Converter` arguments.

### Phase 9: Add The Introspection And Draft-Spec Layer

- [ ] Sample decoded payloads per topic without requiring a full conversion run.
- [ ] Enumerate field paths and nested structures from normalized payloads.
- [ ] Infer leaf kinds, likely dtypes, shape hints, nullability, and image-like payloads.
- [ ] Generate editable draft specs for a chosen row strategy and selected topics.
- [ ] Emit assumptions, warnings, and confidence hints instead of pretending inference is perfect.
- Testing / debug: add unit tests for field-path enumeration and inference heuristics, then use one unfamiliar MCAP fixture to draft a spec and confirm that only config edits are needed to finish the conversion.

### Phase 10: Rework Templates, Notebook, And Docs Around Config-First Authoring

- [ ] Keep `doom_ros_train_py_compatible` as a worked example, not as the primary product surface.
- [ ] Keep at least one generic starter template for simple single-trigger sensor logs.
- [ ] Rewrite `core_demo.ipynb` around inspect, draft, edit, preview, and convert.
- [ ] Document how to override a drafted or built-in spec without defining custom Python functions.
- Testing / debug: add one end-to-end smoke test that starts from inspection, drafts a spec, edits it to a Doom-compatible contract, and converts successfully.

## Phase 1: Strengthen The Schema-Aware Config Model

The first implementation step is to define a config object that is expressive enough for arbitrary training contracts and ergonomic enough to be authored as data.

Recommended model families:

- `ConversionSpec`
- `InputDiscoverySpec`
- `DecodingSpec`
- `RowStrategySpec`
- `AssemblySpec`
- `FeatureSpec`
- `FeatureSourceSpec`
- `TransformSpec`
- `LabelSpec`
- `SplitSpec`
- `ValidationSpec`
- `OutputSpec`

### Tasks

- Add schema models for row strategies instead of coupling schema-aware conversion to trigger assembly only.
- Add schema models for feature sources that can reference paths, constants, metadata, and composed values.
- Add schema models for dtype, shape, required, and missing-data policy.
- Add schema models for transforms, label derivation, and preview settings.
- Keep the current `MappingTemplate` and `ResampleConfig` as compatibility inputs.
- Add `ConversionSpec` JSON and YAML helpers so users can save and edit specs without writing Python builder functions.

### Compatibility Rule

The old `mapping` and `resample` inputs should map onto the new spec when the user does not need the richer schema.

That preserves the current backend and Python API while opening the door to more specific training contracts.

## Phase 2: Split The Pipeline Into Explicit Runtime And Authoring Stages

The converter should stop treating authoring and execution as the same job.

Recommended stage objects or modules:

- discovery
- decoding
- inspection
- row construction
- feature assembly
- transform and encoding
- preview
- validation
- writing
- reporting

### Tasks

- Extract input discovery into its own helper that expands paths, globs, recursion, and topic filters.
- Extract message decoding into a dedicated decoder that can handle ROS2 schema detection and manual type hints.
- Add an inspection module that samples decoded payloads and produces field-level summaries.
- Extract row construction into a strategy layer that supports trigger, per-message, and resampled layouts.
- Keep TFRecord writing focused on serializing already-validated features.

### Current Code Mapping

The current code already suggests a natural split:

- `hephaes/src/hephaes/reader.py` can remain the source-access layer.
- `hephaes/src/hephaes/converter.py` can become the top-level coordinator.
- `hephaes/src/hephaes/outputs/tfrecord_writer.py` can become a pure output sink.
- new inspection and draft-spec modules should sit alongside existing conversion helpers instead of being hidden in the notebook or backend only.

## Phase 3: Generalize Record Construction Beyond Trigger-Only Specs

Trigger-based assembly is still important, but it should not be the only schema-aware path.

### Tasks

- Add a row-strategy config with explicit modes such as `trigger`, `per-message`, and `resample`.
- Allow join topics to resolve relative to each trigger timestamp when trigger mode is used.
- Support `nearest`, `last-known-before`, and `exact-within-tolerance`.
- Add per-topic tolerance and staleness limits.
- Add required versus optional handling for each joined source.
- Emit presence flags when a joined feature is missing.

### Why This Matters

If the user can only use the richer feature contract when they define a trigger topic, then the new schema layer is still narrower than the intended product surface.

The same feature contract should work no matter how rows are created.

## Phase 4: Generalize Feature Sources, Transforms, And Encoding

The converter already has a meaningful transform pipeline, but the feature source model is still too narrow.

### Tasks

- Support source expressions that can read a path, inject a constant, reference metadata, or compose values from multiple sources.
- Keep source paths explicit enough to address nested fields such as `buttons`, `data`, or `header.stamp.sec`.
- Add image transforms for channel conversion, resize, crop, normalization, and image encoding.
- Add numeric transforms for clamp, scale, cast, thresholding, one-hot, and multi-hot encoding.
- Add sequence support for pad, truncate, and ragged handling.
- Add explicit dtype and shape validation before writing.

### TFRecord Writer Rule

`hephaes/src/hephaes/outputs/tfrecord_writer.py` should not guess the meaning of arbitrary nested payloads.

Instead, it should receive a validated feature payload that already knows:

- the final feature name
- the feature dtype
- the feature shape rules
- whether the feature is required or optional
- whether the value was present or synthesized

## Phase 5: Add Validation, Preflight, And Authoring Preview

The user needs guardrails before committing to a long conversion run.

### Tasks

- Add schema compatibility check mode.
- Add sample-N preflight validation.
- Add fail-fast behavior for required feature mismatches.
- Add a bad-record budget.
- Add label distribution reporting.
- Add missing-topic and missing-feature rate reporting.
- Add preview output for assembled rows and extracted features before shard writing.

### Suggested Preflight Flow

1. Resolve inputs and topics.
2. Decode a small sample.
3. Inspect the payload shape.
4. Assemble a small number of rows.
5. Validate feature shapes and dtypes.
6. Preview extracted values.
7. Stop before full writing if any required rule fails.

## Phase 6: Add Sharding, Splitting, And Deterministic Output

The output should be easy to consume from training code and easy to reproduce.

### Tasks

- Add sharding support for TFRecord output.
- Support GZIP and uncompressed output.
- Add deterministic ordering and seed-based randomization when needed.
- Add file naming templates.
- Add train, val, and test split handling.

### Naming Recommendation

Use a naming convention that works well with common training pipelines, such as:

- `train-00000-of-00008.tfrecord`
- `val-00000-of-00002.tfrecord`
- `test-00000-of-00002.tfrecord`

## Phase 7: Update The Manifest And Conversion Report

The manifest should become a schema and audit record, not just a pointer to files.

### Tasks

- Add schema name and version.
- Add resolved feature definitions.
- Add per-feature missing rates.
- Add record counts and dropped counts.
- Add split counts.
- Add validation summary.
- Add row-strategy metadata.
- Add draft-origin metadata when the spec came from a generated draft.
- Keep the existing source metadata and temporal metadata.

### Suggested Report Outputs

- sidecar manifest JSON
- human-readable conversion report
- sample preview output when preview mode is used
- draft assumptions and warnings when the run started from an inferred spec

## Phase 8: Update The Backend Conversion And Authoring Contract

The backend currently accepts richer conversion specs, but it still does not help the user create them.

### Tasks

- Extend `backend/app/schemas/conversions.py` with richer config fields.
- Update `backend/app/services/conversions.py` to build the new conversion spec.
- Preserve the current request shape where possible by translating legacy fields into the new config model.
- Add backend surfaces for inspection, draft-spec generation, and preview.
- Keep the backend validation aligned with the library validation so users get consistent errors.

## Phase 9: Add The Introspection And Draft-Spec Layer

This is the missing bridge between "any MCAP" and "editable training contract."

### Tasks

- Add a topic inspection flow that samples decoded messages and normalizes payloads.
- Enumerate nested field paths and summarize candidate leaves.
- Infer candidate dtypes, shape hints, nullability, and image-like payload signatures.
- Draft row strategies from user input such as trigger topic, per-message topic, or resample target.
- Draft feature definitions that the user can edit instead of writing from scratch.
- Emit warnings and confidence hints when the inference is uncertain.

### Companion Doc

Implementation details for this layer live in:

- [`converter-introspection-and-draft-spec.md`](./converter-introspection-and-draft-spec.md)

## Phase 10: Rework Templates, Notebook, And Docs Around Config-First Authoring

Built-in templates still help, but they should no longer define the core product story.

### Tasks

- Keep `doom_ros_train_py_compatible` as a worked example of the generic spec system.
- Keep at least one generic starter template for simple single-trigger sensor logs.
- Rewrite `core_demo.ipynb` to demonstrate inspect, draft, edit, preview, and convert.
- Document how to override a drafted or built-in spec with custom transforms, labels, or output rules.

## File-Level Plan

| File | Planned change |
| --- | --- |
| `hephaes/src/hephaes/models.py` | Add richer schema-aware config models, feature-source unions, and draft metadata |
| `hephaes/src/hephaes/converter.py` | Convert from generic orchestration to stage-based orchestration with preview support |
| `hephaes/src/hephaes/reader.py` | Keep raw message access and decoded sample access focused and predictable |
| `hephaes/src/hephaes/conversion/introspection.py` | Add payload inspection, field-path enumeration, and inference helpers |
| `hephaes/src/hephaes/conversion/draft_spec.py` | Turn inspection results into editable conversion-spec drafts |
| `hephaes/src/hephaes/conversion/features.py` | Support richer feature-source evaluation and shape validation |
| `hephaes/src/hephaes/outputs/tfrecord_writer.py` | Write validated feature contracts instead of flattening arbitrary payloads |
| `hephaes/src/hephaes/manifest.py` | Record schema, split, validation, preview, and draft-origin metadata |
| `backend/app/schemas/conversions.py` | Expand the API request and response contract |
| `backend/app/services/conversions.py` | Translate request payloads into the richer converter spec and authoring flows |
| `backend/app/api/` | Add inspection, draft-spec, and preview endpoints if the backend owns those flows |
| `hephaes/demo/core_demo.ipynb` | Teach config-first authoring instead of preset-first authoring |
| `backend/tests/` | Add draft-spec tests, validation tests, preview tests, and conversion tests |

## Test Plan

### Unit Tests

- config parsing and validation
- feature-source resolution
- sync policy behavior
- transform behavior
- missing-data policy behavior
- field-path enumeration
- type and shape inference heuristics
- draft-spec generation

### Integration Tests

- inspection output for an unfamiliar MCAP fixture
- draft-spec generation from topic samples
- Doom-compatible conversion using an edited draft instead of a custom builder function
- TFRecord output round-trip through `stream_tfrecord_rows`
- manifest contents and stats
- split and shard naming

### Negative Tests

- missing required feature
- invalid dtype
- shape mismatch
- decode failure with each fallback mode
- bad-record-budget exhaustion
- draft-spec request with insufficient sampling information
- incorrect image-like inference falling back to a warning instead of a silent bad draft

## Acceptance Criteria

- A user can inspect an unfamiliar MCAP and get a useful field-level summary.
- A user can draft a conversion spec as data without defining a custom Python function.
- The drafted spec can be edited into a Doom-compatible training contract using declarative config only.
- The converter can still handle generic MCAP logs and legacy mapping configs.
- Validation fails before full conversion when the output contract is wrong.
- The manifest and report show enough information to audit a conversion run later.
- Backend and library config shapes stay aligned.

## Open Implementation Risks

- Auto-detecting ROS2 schemas may depend on the exact message definition availability in the bag.
- Image-like inference can be helpful, but it must stay transparent about uncertainty.
- Trigger-based assembly can use a lot of memory if the implementation buffers too much per topic.
- Draft generation heuristics can accidentally overfit to the sample window if sampling is too shallow.
- Split logic must remain deterministic so runs are reproducible.
