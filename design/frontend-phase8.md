# Frontend Phase 8

## Goal

Add a dedicated visualization workflow so users can choose a file, open an episode viewer, scrub through synchronized multi-modal data, and replay it in the browser.

## Depends On

- [frontend-phase3.md](/Users/danielyoo/workspace/hephaes/design/frontend-phase3.md) for indexed topic and modality metadata
- [frontend-phase7.md](/Users/danielyoo/workspace/hephaes/design/frontend-phase7.md) for stable app state and navigation continuity
- [backend-phase2.md](/Users/danielyoo/workspace/hephaes/design/backend-phase2.md) for indexed topic and episode summaries
- [backend-phase7.md](/Users/danielyoo/workspace/hephaes/design/backend-phase7.md) for aggregated asset detail and episode discovery
- [backend-phase8.md](/Users/danielyoo/workspace/hephaes/design/backend-phase8.md) for scrubber and playback APIs
- [backend-phase9.md](/Users/danielyoo/workspace/hephaes/design/backend-phase9.md) for official Rerun viewer-source delivery
- [frontend-ui-guidelines.md](/Users/danielyoo/workspace/hephaes/design/frontend-ui-guidelines.md)

## Product Scope

Implement:

- a `Visualize` action from inventory rows and asset detail pages
- an asset-to-episode selection flow when a file exposes more than one episode
- a dedicated visualization page route
- playback transport controls for play, pause, seek, step, and speed changes
- a multi-row scrubber aligned on one shared timeline
- synchronized replay across selected streams or modality lanes
- a reusable component that embeds the official open-source Rerun viewer from `rerun-io/rerun`
- loading, empty, unsupported-data, and backend-error states

The visualization experience should still feel minimal and product-consistent. Use shadcn layout and control primitives around the Rerun viewer shell, and make sure the page works in both light and dark themes.

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

### Shared Rerun viewer component

- wrapper around the official Rerun web viewer package or its React wrapper
- accepts a backend-provided viewer source manifest or URL instead of raw image or point payload props
- handles viewer loading, missing-source, preparation-in-progress, and version-mismatch states
- provides a clear integration seam between the app shell, scrubber state, and the embedded viewer

## State and Data Guidance

Recommended state split:

- URL state for `asset_id`, `episode_id`, selected lanes, current timestamp, and playback speed
- query/cache state for episode summaries, scrubber timeline windows, synchronized sample windows, and viewer-source manifests
- local UI state for play/pause, drag interactions, hover state, viewer readiness, and panel layout

Keep the last useful playback context so users can move between inventory, detail, and visualization routes without losing the selected episode or current timeline position unnecessarily.

The visualization page should not require the browser to parse raw `.bag` or `.mcap` files directly. It should consume backend-provided episode, timeline, and sample APIs plus a backend-provided official Rerun viewer source.

The main visual panel should prefer the official Rerun viewer source over custom rendering of normalized sample payloads. Sample APIs remain useful for scrubber-adjacent UI, inspectors, and fallback states.

## Backend Endpoints Used

- `GET /assets`
- `GET /assets/{asset_id}`
- `GET /assets/{asset_id}/episodes`
- `GET /assets/{asset_id}/episodes/{episode_id}`
- `GET /assets/{asset_id}/episodes/{episode_id}/timeline`
- `GET /assets/{asset_id}/episodes/{episode_id}/samples`
- `GET /assets/{asset_id}/episodes/{episode_id}/viewer-source`
- `POST /assets/{asset_id}/episodes/{episode_id}/prepare-visualization`
- `GET /jobs/{job_id}`

## Deliverable

By the end of phase 8, a user should be able to:

- choose a registered file from the inventory or asset detail page and open it for visualization
- select an episode when multiple episodes are available
- scrub through a shared episode timeline with multiple aligned rows
- replay synchronized multi-modal data in one view
- inspect supported visual data through an embedded official Rerun viewer backed by a backend-provided source

## Execution Split

Phase 8 is intentionally split into smaller frontend phases to keep each PR reviewable and lower risk:

- [frontend-phase8a.md](frontend-phase8a.md) for entry points, routing, API foundations, and visualization shell
- [frontend-phase8b.md](frontend-phase8b.md) for transport controls, timeline model, multi-row scrubber, and inspector synchronization
- [frontend-phase8c.md](frontend-phase8c.md) for official Rerun viewer embedding, preparation workflow, and cross-surface polish

Use this file as the umbrella scope reference, and execute implementation from the split phase documents above.
