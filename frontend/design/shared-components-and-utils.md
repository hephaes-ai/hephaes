# Shared Components And Utils

## Shared Domain Components

The frontend uses a small layer of shared product-specific components on top of `components/ui/`.

### App-level components

- `app-providers.tsx`: theme, SWR, and feedback composition
- `app-shell.tsx`: header, navigation, layout framing, and global controls
- `backend-status.tsx`: health badge driven by `useHealth()`
- `feedback-provider.tsx`: transient top-of-screen alerts with auto-dismiss
- `theme-provider.tsx`: `next-themes` wrapper plus `d` keyboard shortcut
- `theme-toggle.tsx`: visible header control for light/dark mode

### Shared presentational components

- `empty-state.tsx`: reusable empty-state shell used by inventory, dashboard, outputs, and detail surfaces
- `inline-notice.tsx`: shared inline success, info, and error notice used by form and detail flows
- `metadata-field.tsx`: shared labeled value row used across asset, job, and output detail views
- `output-detail-content.tsx`: shared output detail content used by both the outputs workspace and the dedicated output route

### Status badges

- `asset-status-badge.tsx`: `pending`, `indexing`, `indexed`, `failed`
- `output-availability-badge.tsx`: `ready`, `missing`, `invalid`, and future output availability states
- `workflow-status-badge.tsx`: `queued`, `running`, `succeeded`, `failed`

These badges intentionally centralize both wording and color treatment.

### Tag helpers

`tag-controls.tsx` provides the two shared tag UI pieces:

- `TagBadgeList` for compact read-only or removable tag pills
- `TagActionPanel` for applying existing tags and creating new ones

These are used in both inventory selection flows and asset detail.

### Replay helper

`rerun-viewer.tsx` is a standalone official Rerun embed wrapper that can be reused once the main replay page enables embedded viewing end-to-end.

## SWR Hooks And Mutations

`hooks/use-backend.ts` is the frontend's shared read-hook layer.

### Cache keys

The `backendKeys` object keeps all SWR keys in one place so mutations and revalidation do not drift across pages.

### Hook groups

The hook set can be grouped like this:

- connectivity: `useHealth`
- assets: `useAssets`, `useAsset`
- tags: `useTags`
- conversions: `useConversions`, `useConversion`
- outputs: `useOutputs`, `useOutput`
- output actions: `useOutputActions`, `useOutputAction`, `useCreateOutputAction`
- jobs: `useJobs`, `useJob`
- episodes and replay: `useAssetEpisodes`, `useAssetEpisode`, `useEpisodeViewerSource`, `useEpisodeTimeline`, `useEpisodeSamples`
- mutations with shared cache effects: `usePrepareVisualization`, `useBackendCache`

`usePrepareVisualization` is intentionally not a generic mutation helper. It exists because replay preparation needs both UI state and multi-key revalidation.

### Focused mutation hooks

The recent frontend refactor moved several workflow mutations out of the largest page components and into dedicated hooks:

- `use-index-asset.ts`
- `use-create-conversion.ts`
- `use-scan-directory.ts`
- `use-upload-assets.ts`

Each hook owns its own in-flight state and delegates revalidation through `useBackendCache()` so orchestration components stay thinner.

## API Module

`lib/api.ts` is both the request helper and the source of truth for frontend backend types.

### What it defines

- asset, tag, conversion, job, output, output-action, episode, timeline, sample, and viewer-source types
- request payload types for registration, scanning, tagging, conversion, and replay preparation
- `BackendApiError`
- `getErrorMessage()`
- a shared backend base URL resolver

### Endpoint groups

The module currently covers:

- health
- asset list and detail
- asset indexing and bulk reindex
- asset registration, upload, and directory scan
- tags
- conversions
- jobs
- outputs
- output actions
- episode list and detail
- viewer-source status
- prepare-visualization
- episode timeline
- episode samples

## Utility Modules

### `lib/format.ts`

Formatting helpers used throughout the UI:

- file sizes
- timestamps
- durations
- sentence-case labels
- counts and number formatting
- output format, role, and availability labels
- indexing action labels
- workflow-active checks and shared status classes

### `lib/navigation.ts`

Contains shared route builders plus safe return-navigation handling:

- `buildAssetDetailHref()`
- `buildJobDetailHref()`
- `buildOutputDetailHref()`
- `buildHref()`
- `buildInventoryReplayHref()`
- `resolveReturnHref()`

### `lib/dashboard.ts`

Owns the phase-1 dashboard's client-side aggregation and trend helpers:

- asset, job, conversion, and output summaries
- recent-failure merging
- daily trend bucket shaping

When backend phase 2 lands, this module should shrink toward UI-only shaping instead of owning the primary rollups.

### `lib/outputs.ts`

Provides shared helpers for the outputs workspace:

- `buildOutputsHref()` for filtered drill-down links
- `countOutputsByAsset()` for cross-surface output counts

### `lib/types.ts`

Holds shared UI-layer types that are reused across multiple components:

- `ActiveFilterChip`
- `NoticeMessage`

### `lib/visualization.ts`

Owns replay-link construction through `buildReplayHref()` and the legacy alias `buildVisualizeHref`.

### `lib/local-ui-state.ts`

Provides `usePersistentUiState()` for local-storage-backed UI state. It is available in the codebase but is not a major part of the current route implementations because most important state has been moved into the URL instead.

### `lib/future-workflows.ts`

Defines placeholder types for upcoming higher-order workflows:

- saved searches
- saved selections
- selection scopes
- dataset action scopes

These types are already referenced by the inventory route so future work can build on the current selection model instead of replacing it.

### `lib/utils.ts`

Contains `cn()`, the standard `clsx` plus `tailwind-merge` class combiner used throughout the app.

## UI Primitive Layer

The app's generic building blocks live in `components/ui/`:

- alerts
- badges
- buttons
- cards
- checkboxes
- dialogs
- inputs
- labels
- native selects
- skeletons
- switches
- tables
- textareas

These primitives are the default composition layer for product UI. Most route components avoid hand-rolled low-level controls unless the interaction is domain-specific.

## Styling Utilities And Tokens

Shared styling decisions are split between:

- `components.json`, which records the shadcn registry setup and aliases
- `app/globals.css`, which defines the neutral token palette, light/dark theme values, radius scale, and base transitions

The overall visual system favors:

- neutral surfaces
- restrained accents
- clear state coloring for success, warning, and failure
- small status badges and alert surfaces over heavy custom chrome

## Assets And Static Media

The app shell currently uses two static logo assets under `public/`:

- `robot-head-logo-iso.png`
- `robot-head-logo-dark-bg.png`

The shell swaps between them based on theme so the header stays legible in both light and dark mode.
