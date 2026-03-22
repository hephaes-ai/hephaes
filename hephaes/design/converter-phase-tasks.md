# Converter Phase Tasks

This checklist is the execution companion to [converter-design.md](./converter-design.md) and [converter-implementation.md](./converter-implementation.md).

## Phase 1: Define The Schema Contract

- Add richer config models for input discovery, decoding, assembly, feature mapping, transforms, labels, splitting, output, and validation.
- Preserve the current `mapping`, `resample`, `output`, and `write_manifest` inputs as compatibility fields.
- Add a built-in `doom_ros_train_py_compatible` preset so the training-ready path is easy to discover.
- Testing / debug: add unit tests for config validation, legacy translation, and preset expansion, then run a dry conversion and inspect the manifest for schema name and version fields.

## Phase 2: Separate Input Discovery And Decoding

- Expand file discovery to support explicit paths, glob patterns, recursive directories, topic include/exclude filters, and time windows.
- Add a decoding layer with ROS2 auto-detection, manual type hints, and decode failure policies such as skip, warn, and fail.
- Keep `RosReader` focused on raw log access, topic iteration, and metadata extraction.
- Testing / debug: add tests for discovery edge cases and decode failure behavior, then debug one small MCAP by comparing requested topics against actually decoded topics.

## Phase 3: Implement Trigger-Based Record Assembly

- Add trigger-topic selection so each trigger message becomes one output record.
- Implement join policies for `nearest`, `last-known-before`, and `exact-within-tolerance`.
- Add per-topic tolerance, staleness limits, required flags, optional flags, and missing-data behavior.
- Testing / debug: build synthetic timeline tests for each sync policy, then debug assembled rows by verifying trigger timestamps, joined values, and presence flags.

## Phase 4: Add Feature Mapping, Transforms, And Encoding

- Define explicit features using topic plus field path, output dtype, shape constraints, required status, and transform chains.
- Add image transforms for channel conversion, resize, crop, normalization, and encoding format selection.
- Add numeric transforms, sequence padding and truncation, label derivation, and class mapping support.
- Testing / debug: add round-trip tests for PNG image bytes, `buttons` vectors, numeric casts, and shape validation, then debug a known Doom sample to confirm `image` and `buttons` match the training contract.

## Phase 5: Add Validation, Preflight, And Reports

- Validate dtype and shape before writing any record.
- Add schema compatibility checks, sample-N preflight validation, and fail-fast handling for required feature mismatches.
- Add a bad-record budget, missing-topic rates, label summaries, and dry-run mode.
- Testing / debug: add failure-path tests for missing required features and invalid shapes, then run preflight-only mode and confirm it stops before shard writing when a contract is broken.

## Phase 6: Add Sharding, Splitting, And Deterministic Output

- Add shard counts, file naming templates, GZIP or uncompressed output, and deterministic ordering.
- Support train/val/test splits with time-based or random strategies and a fixed seed.
- Keep shard and split outputs stable across reruns so results are easy to compare.
- Testing / debug: add tests that verify shard naming, split assignment stability, and repeated-run determinism, then rerun the same fixture twice and diff the emitted outputs.

## Phase 7: Update The Backend Request And Service Flow

- Extend `backend/app/schemas/conversions.py` to accept the richer converter config.
- Translate legacy backend requests into the new converter spec when possible.
- Align backend validation errors with library validation errors so the user sees one consistent contract.
- Testing / debug: add API tests for both legacy and new payload shapes, plus failure cases for invalid schema contracts, then trace one conversion request from API payload to `Converter` arguments.

## Phase 8: Final Polish And Documentation

- Add end-to-end examples for the Doom preset and at least one generic custom preset.
- Update the root `README.md` and package `hephaes/README.md` if they still describe the old generic-only TFRecord path.
- Retire any obsolete assumptions in the current TFRecord flattening path after the new contract-aware path is stable.
- Testing / debug: run the full test suite plus one manual Doom preset conversion, then debug any manifest, writer, or compatibility regressions before marking the work complete.

