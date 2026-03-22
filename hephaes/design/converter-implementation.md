# MCAP To TFRecord Conversion Implementation Plan

## Overview

This document turns the converter design into a concrete implementation plan for the current `hephaes` codebase.

The present implementation is already useful, but it is still organized around a generic mapping model:

- `hephaes/src/hephaes/reader.py` reads raw or decoded messages
- `hephaes/src/hephaes/converter.py` resolves a topic mapping and resampling mode
- `hephaes/src/hephaes/outputs/tfrecord_writer.py` flattens payloads into TFRecord examples
- `hephaes/src/hephaes/manifest.py` writes a generic manifest
- `backend/app/schemas/conversions.py` exposes a backend request with mapping and resampling only

The implementation work should keep those current behaviors working while adding schema-aware conversion paths.

## Implementation Strategy

The safest path is to introduce the new config and conversion stages in small steps, then wire the current API through compatibility adapters.

That lets us ship the training-ready workflow without breaking existing users who only need generic export.

## Phase 1: Add A Schema-Aware Config Model

The first implementation step is to define a richer config object.

Recommended new model families:

- `ConversionSpec`
- `InputDiscoverySpec`
- `DecodingSpec`
- `AssemblySpec`
- `FeatureSpec`
- `TransformSpec`
- `LabelSpec`
- `SplitSpec`
- `ValidationSpec`
- `OutputSpec`

### Tasks

- Add schema models for trigger-based assembly.
- Add schema models for source paths made of topic plus field path.
- Add schema models for dtype, shape, required, and missing-data policy.
- Add schema models for transforms and label derivation.
- Add schema models for split and validation settings.
- Keep the current `MappingTemplate` and `ResampleConfig` as compatibility inputs.

### Compatibility Rule

The old `mapping` and `resample` inputs should map onto the new spec when the user does not need the richer schema.

That preserves the current backend and Python API while opening the door to more specific training contracts.

## Phase 2: Split The Conversion Pipeline Into Explicit Stages

The next step is to stop doing all conversion work inside one orchestration method.

Recommended stage objects or modules:

- discovery
- decoding
- synchronization
- feature assembly
- transform and encoding
- writing
- validation
- reporting

### Tasks

- Extract input discovery into its own helper that expands paths, globs, recursion, and topic filters.
- Extract message decoding into a dedicated decoder that can handle ROS2 schema detection and manual type hints.
- Extract record assembly into a synchronizer that supports trigger topics and join policies.
- Extract feature assembly into a builder that resolves source paths and evaluates transform chains.
- Keep TFRecord writing focused on serializing already-validated features.

### Current Code Mapping

The current code already suggests a natural split:

- `hephaes/src/hephaes/reader.py` can remain the source-access layer
- `hephaes/src/hephaes/converter.py` can become the top-level coordinator
- `hephaes/src/hephaes/outputs/tfrecord_writer.py` can become a pure output sink

## Phase 3: Implement Trigger-Based Record Assembly

This is the most important behavior change for training compatibility.

### Tasks

- Add a trigger topic to the converter config.
- Allow join topics to resolve relative to each trigger timestamp.
- Support `nearest`, `last-known-before`, and `exact-within-tolerance`.
- Add per-topic tolerance and staleness limits.
- Add required versus optional handling for each joined source.
- Emit presence flags when a joined feature is missing.

### Doom Preset

The first trigger-based preset should target the Doom training layout.

Required output contract:

- `image` must be PNG bytes in RGB order
- `buttons` must be an `int64` vector of length `15`

Recommended rules:

- use `/doom_image` as the trigger
- use `/joy` as a join topic
- forward-fill the most recent joy message before the trigger timestamp
- zero-fill the buttons vector before the first joy message
- keep metadata such as timestamp and source topics as optional extras

## Phase 4: Add Feature Transform And Encoding Support

Once records are assembled correctly, the converter needs a real feature pipeline.

### Tasks

- Add image transforms for channel conversion, resize, crop, normalization, and image encoding.
- Add numeric transforms for clamp, scale, cast, thresholding, one-hot, and multi-hot encoding.
- Add sequence support for pad, truncate, and ragged handling.
- Add explicit dtype and shape validation before writing.

### TFRecord Writer Change

`hephaes/src/hephaes/outputs/tfrecord_writer.py` should stop guessing the meaning of arbitrary nested payloads.

Instead, it should receive a validated feature payload that already knows:

- the final feature name
- the feature dtype
- whether the feature is required or optional
- whether sequence metadata is needed

The writer should stay responsible only for TF Example serialization and checksum-safe file writing.

## Phase 5: Add Validation, Preflight, And Reporting

The user asked for guardrails, so those should be first-class implementation tasks rather than a later add-on.

### Tasks

- Add schema compatibility check mode.
- Add sample-N preflight validation.
- Add fail-fast behavior for required feature mismatches.
- Add a bad-record budget.
- Add label distribution reporting.
- Add missing-topic and missing-feature rate reporting.

### Suggested Preflight Flow

1. Resolve inputs and topics.
2. Decode a small sample.
3. Assemble a small number of trigger records.
4. Validate feature shapes and dtypes.
5. Validate the output contract.
6. Stop before full writing if any required rule fails.

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
- Keep the existing source metadata and temporal metadata.

### Suggested Report Outputs

- sidecar manifest JSON
- human-readable conversion report
- sample preview output when preview mode is used

## Phase 8: Update The Backend Conversion Contract

The backend currently sends `mapping`, `output`, `resample`, and `write_manifest`.

That is too small for the new feature set.

### Tasks

- Extend `backend/app/schemas/conversions.py` with richer config fields.
- Update `backend/app/services/conversions.py` to build the new conversion spec.
- Preserve the current request shape where possible by translating the legacy fields into the new config model.
- Keep the backend validation aligned with the library validation so users get consistent errors.

## Phase 9: Add Built-In Templates

Built-in templates reduce setup friction and make the training-friendly path discoverable.

### Tasks

- Add `doom_ros_train_py_compatible`.
- Add at least one generic template for single-trigger sensor logs.
- Document how to override a built-in template with custom transforms or labels.

## File-Level Plan

| File | Planned change |
| --- | --- |
| `hephaes/src/hephaes/models.py` | Add schema-aware config models and validation types |
| `hephaes/src/hephaes/converter.py` | Convert from generic orchestration to stage-based orchestration |
| `hephaes/src/hephaes/mappers.py` | Keep as compatibility helper for topic alias mapping |
| `hephaes/src/hephaes/outputs/tfrecord_writer.py` | Write validated feature contracts instead of flattening arbitrary payloads |
| `hephaes/src/hephaes/manifest.py` | Record schema, split, validation, and stats metadata |
| `backend/app/schemas/conversions.py` | Expand the API request and response contract |
| `backend/app/services/conversions.py` | Translate request payloads into the richer converter spec |
| `backend/tests/` | Add Doom preset tests, validation tests, and preflight tests |

## Test Plan

### Unit Tests

- config parsing and validation
- feature source-path resolution
- sync policy behavior
- transform behavior
- missing-data policy behavior

### Integration Tests

- Doom preset end-to-end conversion
- TFRecord output round-trip through `stream_tfrecord_rows`
- manifest contents and stats
- split and shard naming

### Negative Tests

- missing required feature
- invalid dtype
- shape mismatch
- decode failure with each fallback mode
- bad-record-budget exhaustion

## Acceptance Criteria

- The new converter can emit a training-ready Doom TFRecord set without post-processing.
- The converter can still handle generic MCAP logs and legacy mapping configs.
- Validation fails before full conversion when the output contract is wrong.
- The manifest and report show enough information to audit a conversion run later.
- Backend and library config shapes stay aligned.

## Open Implementation Risks

- Auto-detecting ROS2 schemas may depend on the exact message definition availability in the bag.
- Image transforms should be tested carefully so RGB byte order and PNG encoding match the training script.
- Trigger-based assembly can use a lot of memory if the implementation buffers too much per topic.
- Split logic must remain deterministic so runs are reproducible.

