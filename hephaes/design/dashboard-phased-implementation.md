# Dashboard Phased Implementation

## Summary

`hephaes` does not need to own the dashboard UI, but it is the right place to own the reusable metric extraction primitives that make deeper robotics dashboard metrics trustworthy.

At the repo's current state, `hephaes` already provides enough information for baseline rollups:

- temporal metadata through `Profiler`
- topic metadata and message counts
- conversion manifest metadata such as dataset rows and fields

That is enough to support backend summaries like:

- recorded duration
- message count
- topic count
- dataset rows written
- dataset field names

It is not yet enough to support richer quality and ML-readiness metrics in a clean, reusable way.

## Current Status

Phase 1 is complete in `hephaes`.

That work landed as:

- `src/hephaes/metrics.py`
- downstream usage in `backend/app/services/indexing.py`
- coverage in `tests/test_metrics.py`

Phases 2 through 4 remain future work.

## Current Seams In `hephaes`

Relevant modules today:

- `src/hephaes/profiler.py`
- `src/hephaes/metrics.py`
- `src/hephaes/models.py`
- `src/hephaes/manifest.py`
- `src/hephaes/converter.py`

Useful current outputs:

- `BagMetadata`
- `TemporalMetadata`
- `Topic`
- `EpisodeManifest`
- `BagTopicSummary`
- `VisualizationReadinessSummary`
- `DatasetArtifactSummary`
- `ManifestReadinessFlags`

Those are already consumed downstream by the backend indexing and conversion paths.

## Recommended Phases

### Cross-Package Dependency Order

The intended dashboard rollout across packages is:

1. `hephaes` phase 1
2. `frontend` phase 1 and `backend` phase 1
3. `backend` phase 2
4. `frontend` phase 2
5. `hephaes` phase 2
6. `hephaes` phase 3
7. `backend` phase 3
8. `frontend` phase 3
9. `hephaes` phase 4
10. `backend` phase 4 only if live aggregation proves too slow

### Phase 1: Add Pure Metric-Derivation Helpers

Status:

- complete
- backend indexing already imports the phase-1 helpers instead of owning those heuristics itself

Goal:

- expose reusable helpers that derive dashboard-friendly summaries from existing metadata models

Dependencies:

- this phase has no dependency on new frontend or backend dashboard work
- this phase is the shared foundation for backend phase 2 summary routes and backend phase 3 quality rollups

Implemented additions:

- `src/hephaes/metrics.py`
- pure functions that accept `BagMetadata`, `Topic`, or `EpisodeManifest`
- no backend-specific imports or storage concerns

Recommended helper outputs:

- modality counts inferred from topic message types
- sensor-family counts
- visualizability summary
- dataset summary from manifest metadata
- readiness flags such as `has_manifest`, `has_rows`, `has_required_fields`

This phase should avoid expensive rescans and should operate on metadata already produced by profiling or conversion.

Exit criteria:

- backend code can call stable helper functions instead of re-deriving dashboard metrics ad hoc

Implementation tasks:

- [x] Create `src/hephaes/metrics.py` as the phase-1 home for dashboard-friendly derivation helpers.
- [x] Implement topic classification helpers such as `infer_topic_modality(message_type)` and `infer_sensor_family(message_type)`.
- [x] Move the current message-type heuristic out of backend indexing and make `hephaes` the source of truth for modality and sensor-family inference.
- [x] Implement a helper that summarizes `BagMetadata.topics` into counts by modality and counts by sensor family.
- [x] Implement a helper that derives visualization-readiness signals from topic summaries, including `has_visualizable_streams` and `visualizable_stream_count`.
- [x] Implement a helper that derives dataset summary signals from `EpisodeManifest`, including format, rows written, field count, and source storage information.
- [x] Implement lightweight readiness-flag helpers from manifest metadata, such as `has_manifest`, `has_rows`, and `has_required_fields`.
- [x] Decide which helpers stay module-local in `hephaes.metrics` for now and which should be imported by downstream callers immediately.
- [x] Add unit tests for empty-topic bags, mixed-modality bags, unknown message types, and manifests with minimal fields only.
- [x] Add regression tests that lock in the current heuristic behavior before downstream layers start depending on it.

### Phase 2: Add Opt-In Quality Profiling

Goal:

- expose richer quality signals without making the default profiler path unexpectedly expensive

Dependencies:

- start this after frontend phase 1 and backend phase 2 have validated which deeper bag-quality signals are worth computing
- this phase unblocks backend phase 3 quality rollups, but it is not required for frontend phase 2

Recommended design:

- keep current `Profiler.profile()` behavior stable
- add optional quality extraction helpers or options rather than silently deepening every profile call

Candidate quality metrics:

- per-topic coverage windows
- topic start and end offsets
- sparse topic warnings
- message-gap heuristics
- approximate synchronization overlap between key modalities

Possible API shapes:

- `extract_quality_metadata(reader)`
- `profile(include_quality=True)`
- a separate `QualityProfile` model that composes with `BagMetadata`

Exit criteria:

- the backend can request deeper quality metrics intentionally
- default profiling cost stays predictable

Implementation tasks:

- [ ] Define phase-2 quality models in `src/hephaes/metrics.py` or a new `src/hephaes/quality.py`, starting with `TopicCoverageSummary`, `MessageGapSummary`, and `QualityProfile`.
- [ ] Add reader-scan helpers that compute per-topic first and last timestamps without changing the default `Profiler.profile()` behavior.
- [ ] Implement opt-in message-gap detection using conservative heuristics so the first version reports obvious sparse or interrupted streams only.
- [ ] Implement approximate overlap metrics for key modalities based on topic coverage windows rather than expensive pairwise alignment logic.
- [ ] Decide and document the public API shape for deeper quality extraction, such as `extract_quality_metadata(reader)` versus `Profiler.profile(include_quality=True)`.
- [ ] Ensure every deeper-quality field is optional so callers can distinguish "not computed" from "computed and empty".
- [ ] Keep expensive scans off by default and add a regression test proving `Profiler.profile()` still returns the same baseline metadata when no quality option is requested.
- [ ] Add tests for zero-message bags, single-topic bags, staggered topic start and stop windows, and obvious large-gap cases.
- [ ] Add at least one benchmark-style test or measurement note to confirm the default profiling path does not take on hidden extra work.

### Phase 3: Enrich Conversion Manifests For Dashboard Use

Goal:

- make dataset-readiness metrics easy to compute from produced artifacts

Dependencies:

- start this after backend phase 2 and frontend phase 2 confirm which readiness signals deserve durable manifest fields
- this phase unblocks backend phase 3 readiness rollups and frontend phase 3 ML-readiness cards

The manifest already stores valuable output information:

- dataset format
- dataset file size
- rows written
- field names
- source metadata
- temporal metadata
- conversion config

Recommended additions, all optional and backward compatible:

- resolved modality summary
- required-field completeness summary
- label coverage summary when labels exist
- scenario or route tags when `robot_context` provides them
- resample summary and null-density summary when cheap to compute

Manifest guidance:

- preserve current fields
- add optional fields rather than changing meaning of existing ones
- bump manifest version only when the contract changes materially

Exit criteria:

- backend output summaries can compute training-readiness metrics from manifests without artifact-specific logic scattered across services

Implementation tasks:

- [ ] Add optional manifest metric sections for dashboard use, such as `modality_summary`, `dataset_quality`, and `readiness_flags`.
- [ ] Implement a helper in `src/hephaes/manifest.py` that builds those optional sections from already-available metadata rather than introducing a second source of truth.
- [ ] Extend `build_episode_manifest()` to accept optional dashboard-oriented metric payloads without breaking existing callers.
- [ ] Update `converter.py` to populate the new optional manifest sections only when the required inputs are already available or cheap to derive.
- [ ] Derive required-field completeness from `field_names` using caller-provided required-field lists rather than hardcoding product policy into `hephaes`.
- [ ] Derive label-coverage summary from `ManifestLabels` when those fields are present, while keeping absence of labels distinct from zero labels.
- [ ] Preserve backward compatibility for older manifests by keeping all new fields optional and validating that old manifests still parse cleanly.
- [ ] Add fixture-based tests for manifests written before and after the new fields are introduced.
- [ ] Add golden-file tests for manifest serialization so the new fields do not accidentally reshape existing payloads.

### Phase 4: Stabilize Public Metric Models

Goal:

- give downstream layers durable typed models for quality and readiness summaries

Dependencies:

- do not freeze these public models until earlier `hephaes` phases have been exercised by backend and frontend consumers
- this phase should follow the first real downstream use of phases 1 through 3 rather than lead it

Recommended models:

- `BagQualitySummary`
- `DatasetQualitySummary`
- `ReadinessFlags`

Model responsibilities:

- stay storage-agnostic
- remain useful to notebooks, scripts, the backend, and future tooling
- keep optional fields explicit so partial extraction is valid

Exit criteria:

- dashboard-related metadata is part of the shared package contract rather than implicit backend logic

Implementation tasks:

- [ ] Promote the phase-1 and phase-2 helper return shapes into stable typed public models, either in `src/hephaes/models.py` or a dedicated exported metrics-model module.
- [ ] Define and document the stable public models, including `BagQualitySummary`, `DatasetQualitySummary`, and `ReadinessFlags`.
- [ ] Export the finalized public models and helpers from `src/hephaes/__init__.py`.
- [ ] Add docstrings and module-level documentation that describe which fields are guaranteed, which are optional, and which are only present when opt-in profiling ran.
- [ ] Add round-trip tests for the public models so serialized metric payloads remain stable across package releases.
- [ ] Add compatibility tests for callers that still import the earlier phase helper locations, and decide whether a deprecation shim is needed.
- [ ] Update package documentation so downstream consumers know when to use raw metadata models versus dashboard-oriented metric models.

## Implementation Notes

The current profiler already scans messages to compute:

- start and end timestamps
- total message count
- per-topic message counts
- topic rates

That makes `hephaes` the right layer for reusable per-bag summaries, especially anything derived from message structure rather than application state.

The manifest layer is also already positioned well for dataset metrics because it writes:

- `rows_written`
- `field_names`
- source artifact details
- conversion config

The shared-package goal should be:

- put metric extraction close to the metadata source
- keep policy and aggregation decisions in the backend
- keep visualization and presentation in the frontend

## Testing Plan

- add unit tests for each pure metric helper
- cover bags with zero messages, one topic, and multiple modalities
- cover manifests with and without optional fields
- add backward-compatibility tests so new optional metric fields do not break existing manifest readers

## Suggested `hephaes` Sequence

1. Add pure derivation helpers over existing models.
2. Let the backend consume those helpers in summary routes.
3. Add opt-in deeper quality profiling once the dashboard proves which signals are actually useful.
4. Extend manifests only for metrics that survive product validation.
