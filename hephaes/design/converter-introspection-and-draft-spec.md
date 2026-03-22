# MCAP Introspection And Draft-Spec Layer

## Summary

This document describes the missing authoring layer for the converter.

The runtime converter is already moving toward a declarative schema contract, but users still need help creating that contract from an unfamiliar MCAP.

The introspection plus draft-spec layer should let a user:

1. inspect topics and decoded payloads
2. explore field paths and likely shapes
3. choose a row-construction strategy
4. generate an editable `ConversionSpec`
5. preview the drafted contract before full conversion

The key product goal is simple:

- users should be able to build a training-ready TFRecord contract for an arbitrary MCAP without defining a custom Python function

## Problem

The current system has a good execution path but a weak authoring path.

Today the user can:

- read topics and decode messages
- define a schema-aware conversion spec
- apply declarative transforms
- run a conversion

Today the user cannot easily:

- inspect nested payload structure for an unfamiliar topic
- enumerate likely field paths
- infer candidate dtypes and shapes from samples
- draft a spec from inspection results
- preview the assembled rows and extracted features before writing shards

That gap forces the workflow back toward custom Python helpers or hand-built specs.

## Goals

- Make converter authoring data-first instead of helper-function-first.
- Support arbitrary MCAP and ROS logs, not just known presets.
- Produce editable draft specs, not opaque one-shot conversions.
- Keep inference transparent with warnings and confidence hints.
- Reuse the same contract shape across Python, backend requests, and a future CLI.
- Keep the runtime conversion path and the authoring path separate but compatible.
- Make `hephaes` the shared business-logic package that backend and frontend can safely build on.

## Non-Goals

- Do not silently infer final labels without the user opting into that.
- Do not pretend a sampled inference is certain when it is only a heuristic.
- Do not hard-code Doom-specific logic into the generic inspection flow.
- Do not make the TFRecord writer responsible for inspection or drafting.

## User Flow

The target workflow should look like this:

```mermaid
flowchart LR
  A["Select MCAP"] --> B["Inspect topics"]
  B --> C["Sample decoded payloads"]
  C --> D["Enumerate field paths"]
  D --> E["Infer candidate features"]
  E --> F["Choose row strategy"]
  F --> G["Generate draft ConversionSpec"]
  G --> H["Edit config"]
  H --> I["Preview rows and features"]
  I --> J["Run full conversion"]
```

This makes presets optional.

Doom compatibility then becomes one example of editing a generic draft into a specific training contract.

## Design Principles

### Declarative First

The output of inspection should be data that the user can save, diff, edit, and send through the backend.

### Transparent Heuristics

If the system guesses that a field is image-like or that a vector is fixed-length, it should say so and include the evidence window it used.

### Small-Sample Friendly

Inspection should work on a shallow sample window so the user can iterate quickly.

### Runtime Separation

Inspection and draft generation should not be entangled with the TFRecord write path.

### Optional Examples

Built-in presets should become examples of a good spec, not a substitute for introspection.

## Business Logic Ownership

The ownership boundaries should be explicit so the product does not fork the same logic across three places.

### `hephaes` Owns

- inspection and inference logic
- draft-spec generation
- preview and validation rules
- config serialization, versioning, and migration
- capability metadata for supported row strategies, source kinds, transforms, dtypes, and preview limits

### Backend Owns

- stable API contracts
- persistence for saved reusable configs, draft revisions, and starter templates
- long-running preview and conversion execution when needed
- resource IDs, history, and access patterns for the frontend

### Frontend Owns

- editor UX
- review and diff UX
- saved-config browsing and selection
- preview presentation
- import and export controls

The frontend should not reimplement inference, validation, migration, or capability rules in TypeScript.

## Proposed Architecture

### Layer Responsibilities

- `reader.py`: raw bag access, decoded message access, topic metadata
- `conversion/decoding.py`: decode policies and type hints
- `conversion/introspection.py`: payload sampling, normalization, field enumeration, inference
- `conversion/draft_spec.py`: convert inspection results into editable `ConversionSpec` drafts
- `conversion/capabilities.py`: publish library-supported row strategies, source kinds, transforms, dtypes, and schema versions
- `conversion/preview.py` or `converter.py`: preview assembled rows and extracted features from a draft
- `converter.py`: execute a fully defined spec

### Suggested Modules

#### `conversion/introspection.py`

Primary responsibilities:

- sample decoded messages per topic
- normalize payloads into dict and list structures
- enumerate nested field paths
- summarize candidate leaves
- infer field kinds, candidate dtypes, and shape hints
- detect image-like payloads

#### `conversion/draft_spec.py`

Primary responsibilities:

- choose a row strategy from user input
- choose included topics and joins
- map selected field candidates into `FeatureSpec` entries
- add starter transforms for obvious cases such as image encoding or numeric casting
- emit assumptions, warnings, and confidence hints

#### `conversion/preview.py`

Primary responsibilities:

- preview assembled rows for a draft
- preview extracted feature values
- preview presence behavior and missing-topic handling
- stop before shard writing

#### `conversion/capabilities.py`

Primary responsibilities:

- expose supported transform kinds
- expose supported source kinds
- expose supported row strategies
- expose current spec version and migration support
- give backend and frontend one stable source for authoring capabilities

## Proposed Data Models

The exact names can change, but the shape should cover the following concepts.

### Inspection Request

- input paths or asset references
- include and exclude topics
- sample count per topic
- max depth for field enumeration
- decode policies and topic type hints
- optional time window

### Topic Inspection Result

- topic name
- message type
- sampled message count
- sample timestamps
- top-level payload summary
- field candidates
- topic-level warnings

### Field Candidate

- `path`
- `kind`
- `examples`
- `nullable`
- `candidate_dtypes`
- `shape_hint`
- `variable_length`
- `image_like`
- `confidence`
- `warnings`

Suggested field kinds:

- `scalar`
- `sequence`
- `struct`
- `bytes`
- `image`
- `unknown`

### Draft Spec Request

- chosen row strategy
- trigger topic or per-message topic if needed
- selected topics
- selected field candidates
- desired output format
- optional output profile such as Doom-compatible image contract

### Draft Spec Result

- `spec`
- `warnings`
- `assumptions`
- `unresolved_fields`
- `preview_ready`

### Saved Reusable Config

- `id`
- `name`
- `description`
- `spec`
- `spec_version`
- `created_from_template`
- `created_from_inspection`
- `tags`
- `created_at`
- `updated_at`

### Draft Revision

- `id`
- `saved_config_id`
- `base_spec_version`
- `draft_spec`
- `status`
- `preview_summary`
- `created_at`

## Row Strategy Drafting

The introspection layer should not force every draft into a trigger-based shape.

Recommended strategies:

- `trigger`
- `per-message`
- `resample`

### Trigger Drafting

Use when:

- one topic is clearly the main observation stream
- other topics should be joined relative to that topic

Draft requirements:

- trigger topic
- join topics
- sync policy defaults
- required or optional join hints

### Per-Message Drafting

Use when:

- the user wants one row per message of a chosen topic
- no temporal join is required at first

Draft requirements:

- main row topic
- optional metadata fields such as timestamp

### Resample Drafting

Use when:

- the user wants a time grid
- multiple streams need to be aligned to a fixed rate

Draft requirements:

- frequency
- interpolation or downsample mode
- per-topic fill behavior

## Field Enumeration And Inference

### Enumeration Rules

The inspector should walk normalized payloads recursively and emit stable field paths such as:

- `buttons`
- `axes`
- `header.stamp.sec`
- `header.stamp.nanosec`
- `data`

For lists:

- summarize leaf element shape and type
- avoid exploding very long index-specific paths unless explicitly requested

### Type Inference Rules

Field inference should stay conservative.

Examples:

- all booleans -> `bool`
- all integers -> `int64`
- mixed integers and floats -> `float32` or `float64` candidate with warning
- bytes buffers -> `bytes`
- nested dicts -> not a leaf feature until the user drills deeper or chooses JSON passthrough

### Shape Inference Rules

The system should distinguish:

- scalar
- fixed-length vector
- variable-length sequence
- fixed-size image-like tensor
- unknown or mixed shape

Shape inference should report the sample basis it used.

### Image-Like Detection

Detection should use transparent heuristics, for example:

- fields named `data`, `pixels`, or `image`
- sibling metadata such as `width`, `height`, `encoding`, or `step`
- byte length matching plausible image shapes
- known encodings from ROS image messages

The result should be a hint, not a silent transform insertion.

## Draft-Spec Generation

The draft generator should create a valid but editable `ConversionSpec`.

### Drafting Rules

- include only selected or obviously relevant topics
- default to optional features unless evidence strongly supports required status
- preserve original topic and field-path references
- add starter transforms only when they are low-risk
- attach assumptions and warnings alongside the draft

### Example Draft Behavior

If inspection sees:

- `/doom_image.data`
- `/doom_image.width`
- `/doom_image.height`
- `/doom_image.encoding = bgra8`
- `/joy.buttons`

the draft generator might produce:

- trigger topic `/doom_image`
- join topic `/joy`
- feature `image` from `/doom_image.data`
- starter transform `image_color_convert` from `bgra` to `rgb`
- starter transform `image_encode` to `png`
- feature `buttons` from `/joy.buttons`

The user should still be able to edit names, transforms, required flags, and output settings in pure config.

## Reusable Configs And Versioning

Reusable configs are part of the product, not just an implementation convenience.

### Requirements

- users should be able to save a config and reuse it later
- users should be able to branch a config into a draft revision
- saved configs should store the authored spec payload, not notebook code
- the backend should own persistence and IDs
- `hephaes` should own spec migration logic when the config schema evolves

### Migration Rule

If a saved config was created against an older spec version:

- the backend should call into `hephaes` migration helpers
- the migrated result should be surfaced back to the user with a clear upgrade note
- preview and conversion should run against the migrated spec, not against stale assumptions

## Capability Metadata

The frontend will need a stable contract for rendering authoring controls.

The backend should expose capability payloads derived from `hephaes`, including:

- supported row strategies
- supported feature source kinds
- supported transform kinds and required params
- supported dtypes
- preview limits and sampling defaults
- current spec version and migration support

This avoids duplicating converter enums and validation logic in React forms.

## Preview Design

Preview is the bridge between inferred draft and committed conversion.

Preview should show:

- sample assembled rows
- feature names and presence flags
- extracted values or short summaries
- missing-source behavior
- transform output shapes
- warnings that remain unresolved

Preview should not write final shards.

## Backend And API Surface

If the backend owns authoring workflows, it should expose separate surfaces for:

- topic inspection
- field-level inspection for one topic
- draft-spec generation
- preview for a draft spec
- capability metadata
- saved reusable configs
- draft revisions

Suggested endpoint shapes:

- `POST /inspections/topics`
- `POST /inspections/fields`
- `POST /draft-specs`
- `POST /draft-specs/preview`
- `GET /conversion-capabilities`
- `GET /conversion-configs`
- `POST /conversion-configs`
- `GET /conversion-configs/{config_id}`
- `PATCH /conversion-configs/{config_id}`
- `POST /conversion-configs/{config_id}/drafts`

Exact route names can change, but the backend should not overload conversion submission with inspection concerns.

## File-Level Architecture Map

| File | Responsibility |
| --- | --- |
| `hephaes/src/hephaes/reader.py` | decoded message access and topic metadata |
| `hephaes/src/hephaes/conversion/decoding.py` | decode policies and type hints |
| `hephaes/src/hephaes/conversion/introspection.py` | payload inspection and inference |
| `hephaes/src/hephaes/conversion/draft_spec.py` | draft generation |
| `hephaes/src/hephaes/conversion/capabilities.py` | business-logic capability metadata |
| `hephaes/src/hephaes/conversion/features.py` | runtime feature extraction from finalized sources |
| `hephaes/src/hephaes/converter.py` | preview and final conversion orchestration |
| `backend/app/db/models.py` | saved reusable config and draft-revision persistence |
| `backend/app/schemas/` | inspection, draft, preview, capability, and saved-config contracts |
| `backend/app/services/` | inspection, draft, preview, migration, and persistence orchestration |
| `backend/app/api/` | authoring and reusable-config endpoints |
| `frontend/lib/api.ts` | typed authoring and reusable-config API client |
| `frontend/app/convert/` | authoring flow, saved-config selection, and preview UX |
| `frontend/components/` | config editor, preview panels, and saved-config management UI |
| `hephaes/demo/core_demo.ipynb` | config-first authoring demo |

## Implementation Tasks

### Phase 1: Add Inspection Result Models

- [ ] Define topic-inspection, field-candidate, and draft-result models.
- [ ] Define confidence, warning, and assumption payload shapes.
- [ ] Define request models for sampling depth, topic filters, and row-strategy hints.
- [ ] Define saved-config and draft-revision models that backend persistence can wrap.

### Phase 2: Implement Payload Sampling And Field Enumeration

- [ ] Sample decoded messages per topic.
- [ ] Normalize payloads into dict and list structures.
- [ ] Enumerate nested field paths.
- [ ] Summarize sequences without exploding large arrays.

### Phase 3: Implement Type, Shape, And Image-Like Inference

- [ ] Infer candidate scalar types.
- [ ] Infer fixed versus variable sequence lengths.
- [ ] Detect image-like payloads from structure and metadata.
- [ ] Attach warnings when evidence is mixed.

### Phase 4: Implement Draft-Spec Generation

- [ ] Draft row strategies.
- [ ] Draft feature definitions from selected candidates.
- [ ] Add low-risk starter transforms.
- [ ] Preserve unresolved assumptions for user review.
- [ ] Keep generated drafts stable and serializable so they can be saved and reopened.

### Phase 5: Implement Preview

- [ ] Preview assembled rows from a draft.
- [ ] Preview feature extraction and transform outputs.
- [ ] Surface missing-data behavior and warnings before write.

### Phase 6: Wire Backend And Notebook Flows

- [ ] Add backend request and response schemas.
- [ ] Add backend services or endpoints for inspection, drafting, and preview.
- [ ] Add backend resources for saved configs and draft revisions.
- [ ] Add capability metadata endpoints backed by `hephaes`.
- [ ] Rewrite `core_demo.ipynb` to demonstrate inspect, draft, edit, preview, and convert.

### Phase 7: Wire Frontend Authoring Flows

- [ ] Add typed frontend API helpers for inspection, draft, preview, capability, and saved-config endpoints.
- [ ] Build conversion-page authoring flows around backend-owned contracts.
- [ ] Add saved-config selection, save, duplicate, and update actions.
- [ ] Keep frontend validation focused on UX-only checks while relying on backend and `hephaes` for semantic validation.

### Phase 8: Add Tests And Acceptance Fixtures

- [ ] Add unit tests for enumeration and inference heuristics.
- [ ] Add integration tests for draft generation from real fixtures.
- [ ] Add backend API tests for saved-config and migration flows.
- [ ] Add frontend contract tests for capability-driven authoring forms if those are covered.
- [ ] Add one smoke test that reaches a Doom-compatible contract through config edits only.

## Test Plan

### Unit Tests

- field-path enumeration for nested dicts and lists
- scalar type inference
- fixed-length versus variable-length shape inference
- image-like detection
- draft generation defaults
- spec migration helpers

### Integration Tests

- inspect a bag with unfamiliar topics and verify useful candidate output
- generate a draft spec from the inspection result
- preview the draft without writing output
- save a reusable config, reopen it, and preview it again
- edit the draft into a final conversion spec and run conversion

### Negative Tests

- mixed-type sequences emit warnings
- sparse or incomplete samples do not force incorrect required flags
- image-like detection falls back to a warning when dimensions are ambiguous
- draft generation fails clearly when the user asks for a trigger topic that is absent
- stale saved configs migrate forward through library-backed rules

## Acceptance Criteria

- A user can inspect an unfamiliar MCAP and understand its candidate feature surface.
- A user can generate a valid draft `ConversionSpec` without writing a custom builder function.
- A user can preview the draft before running a full conversion.
- A user can save, reopen, and reuse a config through backend and frontend flows backed by `hephaes`.
- Doom compatibility can be reached by editing a draft or starter spec, not by defining special Python logic.
- The same draft contract shape can be used from Python and the backend.

## Open Risks

- Sampling too little can make inference misleading.
- Sampling too much can make inspection feel slow and expensive.
- Heuristics that rename features too aggressively can make drafts feel magical and untrustworthy.
- Backend inspection APIs need to stay clearly separate from final conversion submission so failures are easy to reason about.
- Saved-config version drift can become a real product problem unless migration stays centralized in `hephaes`.
