# Realtime Replay And Rerun Sync

## Summary

Replay needs smoother cursor updates, lower-latency payload inspection, and consistent synchronization with the Rerun viewer for images and point clouds.
The backend should keep a REST fallback for cold loads, but active replay should move to a websocket session model backed by bounded bag reads.

## Problem

The current samples path rereads asset data on each request and is optimized for correctness over interactivity.
That is workable for occasional inspection, but it is not a good fit for:

- continuous playback
- scrubber dragging
- synchronized viewer control
- stable payload updates at sub-second cadence

The current behavior also mixes selection concerns:

- visual streams use nearest-sample lookup
- scalar streams can return a time window

That makes it harder to align payload inspection with what the viewer shows at a cursor.

## Goals

- Keep replay responsive during play and drag.
- Make payload updates deterministic and ordered.
- Ensure payload inspection and Rerun viewer state use the same cursor semantics.
- Preserve a simple REST fallback for non-live usage and debugging.
- Reuse prepared `.rrd` viewer sources for the first phase of Rerun integration.

## Non-Goals

- Replace all replay APIs with websocket-only endpoints.
- Introduce a distributed event store.
- Make the first phase depend on a live Rerun gRPC source.

## Recommended Architecture

### 1. Shared Replay Sampling Primitive

Refactor replay sampling around a single bounded-read service that accepts:

- `asset_id`
- `episode_id`
- `cursor_ns`
- selected `stream_ids`
- scalar window settings

That service should use the new `hephaes` time-bounded reads and return a normalized replay payload for both REST and websocket callers.

### 2. Cursor Semantics

Pick one explicit cursor policy for visual streams and validate it against the embedded Rerun viewer during implementation.
The provisional recommendation is:

- images and point clouds resolve to the latest sample at or before the cursor

Keep scalar streams on a bounded window policy:

- scalar series return all samples in the requested time window

This is a better replay default than nearest-sample lookup because it avoids future-looking frames and is more likely to stay aligned with viewer playback semantics.

### 3. Replay Session WebSocket

Add a websocket route for active replay sessions:

- `WS /assets/{asset_id}/episodes/{episode_id}/replay`

Client-to-server messages:

- `hello`
- `set_streams`
- `seek`
- `play`
- `pause`
- `set_speed`
- `set_scalar_window`

Server-to-client messages:

- `ready`
- `cursor_ack`
- `samples`
- `playback_state`
- `error`

Each request and response should carry a monotonically increasing `revision`.
The server should only emit payloads for the latest cursor revision it has accepted for that session.

### 4. Coalescing And Backpressure

The websocket handler should coalesce frequent cursor updates.
If the user drags quickly, the backend should skip obsolete intermediate cursors and compute payloads only for the newest one.

That avoids doing expensive bag reads for stale timestamps that the UI will never render.

### 5. REST Fallback

Keep `GET /samples` for:

- initial loads
- one-off inspection
- testing
- websocket fallback

The REST path should call the same shared replay sampling primitive so both transports stay behaviorally aligned.

### 6. Episode Detail And Stream Bounds

Avoid recomputing stream bounds for every samples request.
Options:

1. cache resolved stream bounds in process by `asset_id + episode_id`
2. persist first and last timestamps during indexing

The first phase can start with in-process caching if the local-first deployment model remains the same.

### 7. Rerun Source Strategy

Phase 1 should continue to use prepared `.rrd` artifacts.
The backend already generates those and serves them as `rrd_url` viewer sources.

That keeps the viewer transport simple while websocket replay improves scrubber responsiveness separately.

The backend viewer-source response should remain the source of truth for:

- `viewer_version`
- `recording_version`
- `source_kind`
- `source_url`

The frontend should only connect with a version-compatible viewer host or embedded viewer package.
Do not depend on an unversioned floating viewer URL for synchronized replay, because the backend currently pins its Rerun SDK version and `.rrd` compatibility is version-sensitive.

### 8. Future Rerun Live Source

A live Rerun source can be added later if needed for:

- session-specific filtering
- server-generated transient overlays
- viewer data that should not be materialized into a static `.rrd`

That should be a separate phase after replay semantics and cursor synchronization are stable.

## Data Contract Notes

The replay payload contract should include:

- `revision`
- `cursor_ns`
- `stream_id`
- `selection_strategy`
- `sample_timestamp_ns`
- `payload`
- `metadata_json`

For visual streams, `selection_strategy` should move from `nearest` to an explicit policy such as `latest_at_or_before`, but the exact value should be finalized only after viewer-sync validation.

## Error Handling

The websocket route should handle:

- missing assets
- missing episodes
- invalid stream IDs
- closed or canceled sessions
- bounded read failures
- reader deserialization failures

Errors should be session-scoped and should not crash the process.

## Rollout Plan

1. Add bounded reads in `hephaes`.
2. Build the shared replay sampling primitive in the backend.
3. Add stream-bound caching or persistence.
4. Switch REST samples to the shared primitive.
5. Add the websocket route with revisioned cursor updates.
6. Update tests for REST and websocket replay behavior.
7. Integrate frontend websocket playback.
8. Integrate Rerun viewer cursor control against the same timeline.

## Implementation Tasks

- [ ] Define the canonical replay cursor semantics for visual and scalar streams.
- [ ] Validate the chosen visual cursor semantics against the embedded Rerun viewer before freezing the contract.
- [ ] Refactor sample lookup into a shared bounded-read replay service.
- [ ] Add in-process caching or persisted storage for stream bounds.
- [ ] Update `GET /samples` to use the shared replay service.
- [ ] Add websocket route and message schemas for replay sessions.
- [ ] Implement revision-based cursor acknowledgements.
- [ ] Implement cursor-update coalescing and stale-work dropping.
- [ ] Return stream payloads with explicit selection strategy values.
- [ ] Add tests for latest-at-or-before visual selection.
- [ ] Add tests for scalar window selection under bounded reads.
- [ ] Add tests for websocket replay session startup, seek, play, and pause.
- [ ] Add tests for stale revision dropping and out-of-order updates.
- [ ] Keep prepared `.rrd` viewer source generation as phase 1 behavior.
- [ ] Ensure viewer-source responses expose the version info the frontend needs to choose a compatible viewer host or package.
- [ ] Document phase 2 criteria for adding a live Rerun source.
