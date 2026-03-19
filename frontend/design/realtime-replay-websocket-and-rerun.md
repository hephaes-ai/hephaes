# Realtime Replay WebSocket And Rerun

## Summary

The replay page should support smooth scrubber dragging and playback while keeping payload inspection synchronized with the Rerun viewer.
The frontend should use websocket-driven replay updates for active interaction and drive the Rerun viewer from the same replay cursor.

## Problem

The current replay page fetches cursor samples through SWR keyed by timestamp and refreshes them while playing or dragging.
That works, but it is not ideal for continuous interaction.

The current viewer integration is also conservative:

- the page uses a backend-prepared viewer source
- the viewer wrapper is currently an iframe-based embed
- the embedded viewer is still disabled in the main replay shell

That setup makes it harder to keep the scrubber, payload panel, and viewer perfectly in sync.

## Goals

- Make playback and scrubber drag feel continuous.
- Avoid rendering stale payloads after rapid cursor changes.
- Use one replay cursor for both payload inspection and Rerun visualization.
- Keep a clean fallback path when websocket replay is unavailable.

## Non-Goals

- Rebuild the entire replay page around the viewer alone.
- Remove the lane payload inspector.
- Depend on live gRPC viewer transport in phase 1.

## Recommended Frontend Architecture

### 1. Split Cold Load From Active Replay

Use REST for:

- initial asset and episode loading
- initial timeline and viewer-source loading
- websocket fallback

Use websocket for:

- active seek updates
- playback state
- cursor-scoped payload delivery

### 2. Replay Client State

Keep local UI state for:

- `isPlaying`
- `speed`
- `currentTimestampNs`
- `selectedLaneIds`
- `isScrubberDragging`

Add replay transport state for:

- `connectionStatus`
- `lastSentRevision`
- `lastAckedRevision`
- `lastPayloadRevision`
- `serverPlaybackState`

The UI should only render websocket payloads whose revision matches the latest accepted cursor revision.

### 3. Cursor Update Strategy

During drag and playback:

- update the visible scrubber cursor immediately in local state
- send cursor updates through the websocket
- let the backend coalesce rapid updates
- keep the last confirmed payload visible until the next matching revision arrives

On pointer-up:

- send a final high-priority cursor update
- ensure payloads settle on that exact final cursor

### 4. Payload Rendering Rules

The payload panel should:

- show current confirmed payloads
- show a lightweight updating state while a newer cursor revision is in flight
- ignore late websocket payloads for stale revisions

This is better than clearing payloads on every cursor move.

### 5. Rerun Viewer Integration

Replace the iframe wrapper with the official controllable web viewer API when phase 1 viewer embedding is turned on.
The frontend should:

- load the backend-prepared `.rrd` source
- use a viewer package or hosted viewer version that matches the backend's reported `viewer_version`
- set the current time from the replay cursor
- set play or pause state from the replay transport state
- optionally listen to viewer time events and reflect user viewer scrubbing back into the replay state

The replay cursor should remain the primary source of truth.
Do not rely on the floating `https://app.rerun.io` host for synchronized replay mode.
Use a version-pinned viewer package or a versioned hosted viewer URL instead.

### 6. Sync Policy

The frontend should not hardcode visual selection semantics on its own.
Instead, it should render the backend-declared `selection_strategy` and keep the viewer at the same `cursor_ns`.
The initial backend target is expected to be:

- visual payloads are resolved as latest-at-or-before the cursor
- scalar lanes may render multiple samples from a bounded window
- the viewer is driven to the same `cursor_ns`

That keeps the payload panel and the visual viewer aligned without requiring the same transport for both.

### 7. Fallback Behavior

If websocket replay fails:

- show a degraded but usable replay mode
- fall back to the existing REST samples path
- keep the viewer source and timeline available

## Component Changes

Likely touch points:

- `frontend/components/visualization-page.tsx`
- `frontend/components/visualization-scrubber.tsx`
- `frontend/components/rerun-viewer.tsx`
- `frontend/hooks/use-backend.ts`
- `frontend/lib/api.ts`

Add a dedicated replay websocket hook or client module instead of embedding transport details directly in the page component.

## Rollout Plan

1. Add websocket replay client support.
2. Integrate revisioned payload updates into the replay page.
3. Keep REST samples as fallback.
4. Replace iframe-based Rerun integration with a controllable viewer wrapper.
5. Drive viewer cursor and play state from replay state.
6. Optionally add viewer-to-scrubber sync for direct timeline interactions inside the viewer.

## Implementation Tasks

- [ ] Add a replay websocket client module or hook.
- [ ] Add connection and revision state to the replay page.
- [ ] Replace polling-style active replay sample refresh with websocket updates.
- [ ] Keep existing REST sample fetch as fallback behavior.
- [ ] Stop clearing payloads on every cursor change; render confirmed payloads until the next revision arrives.
- [ ] Add stale-revision guards so late payloads are ignored.
- [ ] Update scrubber drag behavior to send coalesced cursor updates and a final pointer-up commit.
- [ ] Turn the viewer shell back on once controllable viewer integration is ready.
- [ ] Add the matching `@rerun-io/web-viewer` or `@rerun-io/web-viewer-react` dependency at a version compatible with the backend Rerun SDK.
- [ ] Replace the iframe-only Rerun wrapper with a viewer API wrapper that can set current time and play state.
- [ ] Drive the viewer with the same replay cursor used by the payload inspector.
- [ ] Use backend-provided viewer version metadata to prevent frontend and backend Rerun version drift.
- [ ] Add tests for replay state transitions around play, drag, pause, and reconnect.
- [ ] Add tests for stale websocket payload rejection.
- [ ] Add tests or manual verification notes for viewer and payload synchronization.
