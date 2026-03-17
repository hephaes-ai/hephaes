# Backend Phase 8

## Goal

Expose indexed episode playback data so the frontend can build a visualization page with a multi-row scrubber, synchronized replay, and an official Rerun viewer surface.

## Scope

Make episodes and visual streams first-class backend concepts.

This phase is the playback and scrubber API layer.

The backend should:

- expose discoverable episodes for each indexed asset
- expose stream or lane metadata for each episode
- return scrubber-friendly timeline data aligned to one shared clock
- return synchronized visual samples around a requested timestamp or time window
- optionally cache preview artifacts when on-demand extraction becomes too expensive

The backend should keep the scrubber and sample contracts app-owned and frontend-friendly.

Official Rerun recording generation and delivery should be treated as a separate concern. That work lives in [backend-phase9.md](/Users/danielyoo/workspace/hephaes/design/backend-phase9.md), where the backend prepares a viewer-compatible `.rrd` or equivalent Rerun source for the embedded official viewer.

## Data Model

Introduce tables or persisted records for episode and stream metadata.

Suggested episode fields:

- `id`
- `asset_id`
- `episode_key`
- `label`
- `source_kind`
- `start_time`
- `end_time`
- `duration_seconds`
- `created_at`
- `updated_at`

Suggested stream fields:

- `id`
- `episode_id`
- `stream_key`
- `source_topic`
- `message_type`
- `modality`
- `message_count`
- `rate_hz`
- `first_timestamp`
- `last_timestamp`
- `metadata_json`

Suggested modality values:

- `image`
- `points`
- `scalar_series`
- `other`

Do not require every visual sample to live in SQLite. Large image frames or point payloads can be served from source files or cached artifacts while SQLite stores the indexing metadata needed to discover and request them.

## API Surface

Add or complete these routes:

- `GET /assets/{asset_id}/episodes`
- `GET /assets/{asset_id}/episodes/{episode_id}`
- `GET /assets/{asset_id}/episodes/{episode_id}/timeline`
- `GET /assets/{asset_id}/episodes/{episode_id}/samples`

Suggested behavior:

- `GET /assets/{asset_id}/episodes` returns episode summaries for a selected asset
- `GET /assets/{asset_id}/episodes/{episode_id}` returns episode bounds, stream definitions, and visualization availability
- `GET /assets/{asset_id}/episodes/{episode_id}/timeline` returns lane definitions plus decimated or windowed event positions for the multi-row scrubber
- `GET /assets/{asset_id}/episodes/{episode_id}/samples` accepts a timestamp or time window and returns synchronized samples for one or more requested streams

Suggested query parameters for `GET /assets/{asset_id}/episodes/{episode_id}/samples`:

- `timestamp_ns`
- `window_before_ns`
- `window_after_ns`
- `stream_ids`

## Payload Guidance

Timeline responses should be lightweight enough to support scrubbing without downloading every raw message.

Sample responses should return normalized payload shapes such as:

- image frame bytes or URLs plus width, height, encoding, and timestamp metadata
- point or graph data as arrays plus axis or coordinate metadata
- scalar-series samples as timestamp-value pairs

When a payload is too large for inline JSON, the backend can return a local artifact path or blob endpoint reference instead of embedding the bytes directly.

These sample payloads are primarily for scrubber-adjacent UI, hover state, inspectors, or fallback rendering. They should not be treated as the main integration path for the official Rerun viewer.

## Job and Caching Guidance

Phase 5 already introduces durable jobs. Use that system when you need to:

- precompute thumbnails
- build decimated scrubber summaries
- cache expensive visual extracts

The first implementation can still read directly from the raw asset on demand if that is simpler and fast enough for local use.

## Deliverable

By the end of phase 8, you should be able to:

- discover episodes and visualizable streams for an indexed asset
- fetch the timeline data needed to draw a synchronized multi-row scrubber
- request synchronized samples for replay at a given timestamp
- support frontend visualization workflows without the browser parsing raw bag files directly
- hand off cleanly into the official Rerun-viewer delivery work defined in [backend-phase9.md](/Users/danielyoo/workspace/hephaes/design/backend-phase9.md)

## Implementation Tasks

Phase 8 should stop at episode discovery, scrubber timelines, and synchronized sample access.

Do not make this phase responsible for generating or serving the official Rerun viewer source. That delivery work belongs in [backend-phase9.md](/Users/danielyoo/workspace/hephaes/design/backend-phase9.md).

### Episode and stream contract

- Define the first-cut backend contract for episodes and streams so the frontend can treat them as stable visualization primitives.
- Decide whether phase 8 persists dedicated episode and stream records in SQLite or derives them on demand from indexed metadata plus lightweight cache artifacts.
- Keep the first implementation focused on one shared clock model so scrubber and replay surfaces do not have to reconcile per-stream time bases in the browser.
- Document the minimum modality coverage for the first cut, especially which of these are actually supported end to end:
  - image
  - points
  - scalar series

### Persistence model

- Add episode and stream models in [backend/app/db/models.py](/Users/danielyoo/workspace/hephaes/backend/app/db/models.py) if phase 8 chooses persisted discovery metadata.
- Keep large visual payloads out of SQLite and store only the metadata needed to discover, filter, and request them.
- Include enough persisted metadata for:
  - episode bounds
  - stream definitions
  - modality
  - message counts
  - sample timing bounds
  - visualization readiness
- Decide how episode and stream metadata is refreshed when an asset is reindexed.

### Episode indexing service

- Add a dedicated service module, for example [backend/app/services/episodes.py](/Users/danielyoo/workspace/hephaes/backend/app/services/episodes.py), so playback and discovery logic stays separate from basic asset registration.
- Build episode summaries from indexed metadata first, and only reach into raw files when phase 8 truly needs finer-grained timing or sample extraction.
- Introduce helpers for:
  - listing episodes for an asset
  - fetching one episode definition
  - listing stream or lane definitions for an episode
  - resolving scrubber timeline summaries
  - resolving synchronized samples for a timestamp or window
- Keep the scrubber and sample contracts independent from the official viewer source format so phase 9 can add Rerun-native recording delivery without destabilizing the timeline APIs.

### Timeline generation

- Add a scrubber-oriented timeline response that is lightweight enough for rapid UI interaction.
- Define a response shape for [GET /assets/{asset_id}/episodes/{episode_id}/timeline](/Users/danielyoo/workspace/hephaes/design/backend-phase8.md) that includes:
  - episode bounds
  - lane or stream definitions
  - decimated event markers or buckets
  - shared time units such as nanoseconds
- Decide whether the first cut uses:
  - per-message positions
  - fixed decimation
  - or bucketed summaries
- Keep the payload small enough that opening the visualization page does not require downloading every raw sample.

### Sample extraction

- Implement [GET /assets/{asset_id}/episodes/{episode_id}/samples](/Users/danielyoo/workspace/hephaes/design/backend-phase8.md) for synchronized replay reads.
- Support query parameters for:
  - `timestamp_ns`
  - `window_before_ns`
  - `window_after_ns`
  - `stream_ids`
- Return normalized payloads for the first supported modalities, such as:
  - image sample metadata and a payload reference or inline bytes strategy
  - point or graph arrays with basic coordinate metadata
  - scalar time-series samples as timestamp-value pairs
- Decide how the backend chooses the nearest or aligned sample for each stream around the requested timestamp.
- Keep the route positioned as a complementary data surface for scrubbers, inspectors, and fallback UX rather than the primary transport for the official Rerun viewer.

### Episode detail route

- Implement [GET /assets/{asset_id}/episodes/{episode_id}](/Users/danielyoo/workspace/hephaes/design/backend-phase8.md) as the main episode-definition route.
- Include:
  - episode identity and bounds
  - stream or lane definitions
  - modality metadata
  - visualization availability
  - any preview or cache hints the frontend may need
- Keep the response frontend-friendly so the visualization page can load most of its initial state from one request.

### Caching and jobs

- Decide which expensive visualization-preparation work should stay on-demand and which should be cached locally.
- Reuse the phase 5 jobs system for optional visualization-prep work such as:
  - decimated timeline caches
  - thumbnails
  - image-frame extraction
- Keep official Rerun recording generation separate and version-aware in [backend-phase9.md](/Users/danielyoo/workspace/hephaes/design/backend-phase9.md), even if both phases share the same durable jobs system.
- Keep the first cut working even without precomputed caches, as long as local performance is acceptable.
- If cache artifacts are added, define where they live under backend-managed storage and how they are invalidated.

### API schemas

- Add dedicated episode, stream, timeline, and sample schemas in [backend/app/schemas/assets.py](/Users/danielyoo/workspace/hephaes/backend/app/schemas/assets.py) or a new schema module such as [backend/app/schemas/episodes.py](/Users/danielyoo/workspace/hephaes/backend/app/schemas/episodes.py).
- Keep schemas normalized and backend-owned rather than leaking `hephaes` internal types directly.
- Include enough type information for the frontend to distinguish image, point, and scalar payloads safely.
- Make sure route payloads are explicit about units, especially timestamps and duration values.

### Route implementation

- Add or complete:
  - `GET /assets/{asset_id}/episodes`
  - `GET /assets/{asset_id}/episodes/{episode_id}`
  - `GET /assets/{asset_id}/episodes/{episode_id}/timeline`
  - `GET /assets/{asset_id}/episodes/{episode_id}/samples`
- Keep missing-asset and missing-episode behavior clear and consistent with earlier phases.
- Return readable validation errors for invalid timestamps, invalid stream IDs, and unsupported sample requests.
- Decide whether the first cut supports only indexed assets and make that contract explicit in route behavior.

### Tests

- Add backend tests for episode listing and episode-detail discovery on indexed assets.
- Add tests for missing or unindexed assets across the new episode routes.
- Add tests for timeline responses, including shape, ordering, and shared-clock metadata.
- Add tests for sample retrieval with:
  - a single timestamp
  - a timestamp window
  - selected stream filters
- Add tests for modality-specific sample payloads and any cache-reference behavior.
- Add tests for invalid query params and unsupported stream requests.

### Local verification

- Run the backend locally against a real indexed asset and verify episode discovery works from the new routes.
- Verify the timeline response is small and stable enough for the planned multi-row scrubber.
- Verify sample requests return synchronized results around a chosen timestamp.
- Verify the returned payload shapes are sufficient for the frontend to drive a Rerun-backed viewer without parsing raw bag files in the browser.
- If cache artifacts are introduced, verify they are created, reused, and invalidated predictably.
