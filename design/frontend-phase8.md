# Frontend Phase 8

## Goal

Add a dedicated visualization workflow so users can choose a file, open an episode viewer, scrub through synchronized multi-modal data, and replay it in the browser.

## Depends On

- [frontend-phase3.md](/Users/danielyoo/workspace/hephaes/design/frontend-phase3.md) for indexed topic and modality metadata
- [frontend-phase7.md](/Users/danielyoo/workspace/hephaes/design/frontend-phase7.md) for stable app state and navigation continuity
- [backend-phase2.md](/Users/danielyoo/workspace/hephaes/design/backend-phase2.md) for indexed topic and episode summaries
- [backend-phase7.md](/Users/danielyoo/workspace/hephaes/design/backend-phase7.md) for aggregated asset detail and episode discovery
- [backend-phase8.md](/Users/danielyoo/workspace/hephaes/design/backend-phase8.md) for scrubber and playback APIs
- [frontend-ui-guidelines.md](/Users/danielyoo/workspace/hephaes/design/frontend-ui-guidelines.md)

## Product Scope

Implement:

- a `Visualize` action from inventory rows and asset detail pages
- an asset-to-episode selection flow when a file exposes more than one episode
- a dedicated visualization page route
- playback transport controls for play, pause, seek, step, and speed changes
- a multi-row scrubber aligned on one shared timeline
- synchronized replay across selected streams or modality lanes
- a reusable component that wraps Rerun's open-source web viewer for visual data
- loading, empty, unsupported-data, and backend-error states

The visualization experience should still feel minimal and product-consistent. Use shadcn layout and control primitives around the Rerun component, and make sure the viewer shell works in both light and dark themes.

## Recommended UI Surfaces

### Visualization entry points

- `Visualize` action on indexed asset rows when visualization data is available
- `Visualize` action on the asset detail page
- episode picker dialog or inline selector when an asset exposes multiple episodes

### Visualization page

- asset and episode header with duration, time bounds, and stream counts
- transport controls for play, pause, jump-to-start, jump-to-end, frame step, and playback speed
- multi-row scrubber with one row per selected stream or modality group
- current timestamp indicator shared across scrubber rows and visual panels
- lane toggles so users can hide or show streams without leaving the page
- inspector panel for topic name, message type, timestamp, and per-sample metadata
- theme-aware layout and control styling that keeps the playback surface legible in both modes

### Shared visual data component

- wrapper around the Rerun web component
- normalized props for image frames, point or graph data, and scalar-series overlays
- graceful fallback UI when a stream is indexed but not yet renderable by the Rerun-backed component

## State and Data Guidance

Recommended state split:

- URL state for `asset_id`, `episode_id`, selected lanes, current timestamp, and playback speed
- query/cache state for episode summaries, scrubber timeline windows, and sampled playback data
- local UI state for play/pause, drag interactions, hover state, and panel layout

Keep the last useful playback context so users can move between inventory, detail, and visualization routes without losing the selected episode or current timeline position unnecessarily.

The visualization page should not require the browser to parse raw `.bag` or `.mcap` files directly. It should consume backend-provided episode, timeline, and sample APIs.

## Backend Endpoints Used

- `GET /assets`
- `GET /assets/{asset_id}`
- `GET /assets/{asset_id}/episodes`
- `GET /assets/{asset_id}/episodes/{episode_id}`
- `GET /assets/{asset_id}/episodes/{episode_id}/timeline`
- `GET /assets/{asset_id}/episodes/{episode_id}/samples`

## Deliverable

By the end of phase 8, a user should be able to:

- choose a registered file from the inventory or asset detail page and open it for visualization
- select an episode when multiple episodes are available
- scrub through a shared episode timeline with multiple aligned rows
- replay synchronized image and point or graph data in one view
- inspect supported visual data through a shared Rerun-backed component instead of one-off renderers
