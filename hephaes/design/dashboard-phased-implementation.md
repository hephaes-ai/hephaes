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

## Current Seams In `hephaes`

Relevant modules today:

- `src/hephaes/profiler.py`
- `src/hephaes/models.py`
- `src/hephaes/manifest.py`
- `src/hephaes/converter.py`

Useful current outputs:

- `BagMetadata`
- `TemporalMetadata`
- `Topic`
- `EpisodeManifest`

Those are already consumed downstream by the backend indexing and conversion paths.

## Recommended Phases

### Phase 1: Add Pure Metric-Derivation Helpers

Goal:

- expose reusable helpers that derive dashboard-friendly summaries from existing metadata models

Recommended additions:

- a new module such as `src/hephaes/metrics.py` or `src/hephaes/quality.py`
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

### Phase 2: Add Opt-In Quality Profiling

Goal:

- expose richer quality signals without making the default profiler path unexpectedly expensive

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

### Phase 3: Enrich Conversion Manifests For Dashboard Use

Goal:

- make dataset-readiness metrics easy to compute from produced artifacts

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

### Phase 4: Stabilize Public Metric Models

Goal:

- give downstream layers durable typed models for quality and readiness summaries

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
