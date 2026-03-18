# Frontend Phase 8B

## Goal

Implement synchronized playback behavior, shared timeline controls, and scrubber-driven inspector updates for the visualization workflow.

## Depends On

- [frontend-phase8a.md](frontend-phase8a.md)
- [backend-phase8.md](backend-phase8.md)

## Scope

Implement:

- transport controls and canonical playback state model
- timeline and samples API integration for scrubber and inspector
- multi-row scrubber aligned to one shared timeline cursor
- lane toggle behavior and URL persistence for lane selection
- scoped polling behavior while playback is active

## Tasks

### Playback state model

- Implement canonical visualization playback state containing:
  - isPlaying
  - currentTimestamp
  - speed
  - stepSize
- Keep state deterministic during seek, step, and speed transitions.

### Transport controls

- Implement controls for:
  - play
  - pause
  - jump to start
  - jump to end
  - step backward
  - step forward
  - speed changes
- Ensure controls update a single shared timestamp cursor.

### API and hooks for timeline and samples

- Extend [frontend/lib/api.ts](../frontend/lib/api.ts) with typed support for:
  - GET /assets/{asset_id}/episodes/{episode_id}/timeline
  - GET /assets/{asset_id}/episodes/{episode_id}/samples
- Add hooks in [frontend/hooks/use-backend.ts](../frontend/hooks/use-backend.ts) for:
  - timeline windows
  - synchronized sample windows keyed by timestamp and selected lanes
- Add revalidation helpers for playback-driven fetches.

### Multi-row scrubber

- Build reusable scrubber components under [frontend/components](../frontend/components):
  - one shared timeline axis
  - one row per selected lane or modality group
  - one shared cursor marker
- Support drag seek and click seek interactions.
- Ensure scrubber interactions update transport state and sample queries.

### Lane management

- Add lane visibility toggles on the visualization page.
- Persist selected lanes in URL state so refresh/back restore lane visibility.
- Gracefully handle unavailable lanes returned by backend responses.

### Inspector synchronization

- Implement inspector panel updates from synchronized sample data with fields:
  - topic name
  - message type
  - timestamp
  - sample metadata
- Add partial-data and no-data fallback states.

### Polling behavior

- Poll timeline/samples only when playback is active or user is dragging cursor with continuous updates.
- Stop or reduce polling when paused.
- Keep polling intervals conservative to avoid unnecessary load.

## Deliverable

By the end of phase 8B, users can control playback, scrub synchronized rows, toggle lanes, and see inspector data update coherently from a shared timeline cursor.

## Verification

- verify play/pause/jump/step/speed controls
- verify scrubber cursor and row alignment
- verify lane toggle persistence in URL
- verify inspector updates at cursor changes
- verify polling stops when paused
- run:
  - npm run lint
  - npm run typecheck
  - npm run build
