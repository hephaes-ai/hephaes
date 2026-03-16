# Backend Phase 8

## Goal

Expose indexed episode playback data so the frontend can build a visualization page with a multi-row scrubber, synchronized replay, and Rerun-backed visual rendering.

## Scope

Make episodes and visual streams first-class backend concepts.

The backend should:

- expose discoverable episodes for each indexed asset
- expose stream or lane metadata for each episode
- return scrubber-friendly timeline data aligned to one shared clock
- return synchronized visual samples around a requested timestamp or time window
- optionally cache preview artifacts when on-demand extraction becomes too expensive

The backend should stay Rerun-agnostic. It should provide normalized data and metadata that the frontend can adapt into the Rerun web component.

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
- support frontend visualization of image and point or graph data without the browser parsing raw bag files directly
