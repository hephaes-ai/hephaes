# Replay And Visualization

## Route Structure

Replay currently lives on two route entrypoints:

- `app/replay/page.tsx`: the real visualization route
- `app/visualize/page.tsx`: a compatibility redirect that forwards existing query params into `/replay`

This preserves older links while keeping the product language focused on replay.

## Replay Query Contract

`components/visualization-page.tsx` reads its state from query params:

- `asset_id`
- `episode_id`
- `from`
- `lanes`
- `speed`
- `timestamp_ns`

The page treats the URL as the durable replay state so users can:

- return to a previous replay context
- preserve chosen lanes
- preserve playback speed
- preserve the current timestamp

## Data Loaded For Replay

The replay page composes several backend resources at once:

- asset detail through `useAsset()`
- episode list through `useAssetEpisodes()`
- selected episode detail through `useAssetEpisode()`
- timeline lanes through `useEpisodeTimeline()`
- per-cursor samples through `useEpisodeSamples()`
- viewer-source status through `useEpisodeViewerSource()`
- prepare-visualization mutation through `usePrepareVisualization()`
- linked preparation job through `useJob()`

This route is the densest integration point between the frontend and backend visualization APIs.

## Replay State Model

Local React state is used for transient playback behavior:

- `isPlaying`
- `speed`
- `currentTimestampNs`
- `selectedLaneIds`
- `isScrubberDragging`
- `preparationJobId`

The URL remains the persisted state, while local state smooths playback and interaction between URL updates.

## Episode Resolution

Episode handling follows a few simple rules:

- if the URL already specifies an `episode_id`, use it
- if there is exactly one episode, auto-select it
- if there are multiple episodes and none is selected, show an episode picker
- if an episode has no supported replay streams, show that explicitly rather than silently failing

## Timeline And Scrubber

The main playback surface is `components/visualization-scrubber.tsx`.

### What the scrubber shows

For each replay lane it renders:

- lane label
- modality
- show or hide toggle
- a lane timeline with event or bucket markers
- the current cursor line
- payload disclosure for the current cursor

### Seek behavior

Seeking is pointer-driven:

- pointer down captures the pointer and seeks immediately
- pointer move continues seeking while captured
- pointer up releases capture and commits the final position
- pointer cancel ends drag mode cleanly

### Lane payload inspection

The scrubber shows payload JSON under each lane using a `details` disclosure. Samples are grouped by stream ID and only lanes that are currently selected contribute payloads.

### Playback transport

The replay page also provides:

- start
- play
- pause
- step backward
- step forward
- end
- speed selector

Playback advances the cursor in 100 ms steps, translated to nanoseconds.

## Sample Window Strategy

The replay page requests a symmetric sample window around the cursor:

- `window_before_ns`
- `window_after_ns`

The minimum window is one second and grows to at least ten step sizes. This keeps the scrubber payload view useful while the cursor is moving.

While playback is active or the user is dragging the scrubber, samples are refreshed every 900 ms.

## Viewer Source States

Replay source readiness is treated as a first-class workflow. The page distinguishes:

- waiting for an episode
- loading source state
- source-ready
- preparing
- failed
- version mismatch
- unavailable

If a replay source does not exist yet, the user can trigger `prepare-visualization` directly from the page.

## Prepare Visualization Workflow

The replay page's preparation flow works like this:

1. call `prepareEpisodeVisualization(assetId, episodeId)`
2. capture the returned job ID
3. revalidate the viewer-source state and linked job
4. poll while preparation is active
5. transition the UI once the viewer source becomes ready or fails

The page always keeps the user connected to the linked durable job through a direct job-detail link.

## Current Rerun Integration State

`components/rerun-viewer.tsx` already exists and can build an official Rerun embed URL using:

- `NEXT_PUBLIC_RERUN_VIEWER_HOST`, or
- `https://app.rerun.io` by default

It supports both:

- RRD recording sources
- gRPC stream sources

However, `VisualizationPage` currently keeps the embedded viewer disabled in the page shell even when the source is ready. Instead, the page shows source readiness, artifact path, and source links while leaving the timeline controls and payload inspection active.

That means the current replay implementation is:

- fully wired for timeline browsing and backend source preparation
- partially wired for official viewer embedding
- still intentionally conservative about turning on the embedded viewer in the main route

## Replay Error Handling

The replay route explicitly handles:

- missing asset IDs
- backend 404s and other load failures
- assets with no episodes
- episodes with no visualizable data
- timeline load failures
- viewer-source load failures
- prepare-visualization failures
- version mismatch responses

The design goal is to keep replay controls understandable even when the viewer source is missing or still building.
