# Frontend Architecture

## Purpose

The frontend is a local-first Next.js application for working with registered ROS bag assets. It is designed to stay close to the backend contract instead of introducing a separate frontend domain model. Most screens render backend data directly, with small amounts of client state for view behavior, playback, and in-progress actions.

Core product surfaces currently implemented:

- inventory browsing and ingestion
- asset detail and metadata inspection
- durable job monitoring
- conversion launch and output inspection
- replay timeline browsing and viewer-source preparation

## Stack

The current frontend stack is defined in `frontend/package.json` and `frontend/components.json`.

- Next.js `16.1.6` with the App Router
- React `19.2.4`
- TypeScript in `strict` mode
- Tailwind CSS `4` with shadcn CSS variables
- shadcn UI using the `radix-nova` style preset
- Radix primitives under `components/ui/`
- SWR for request caching and manual revalidation
- `next-themes` for theme persistence and system-theme support
- `lucide-react` for icons

## App Structure

### Route entrypoints

The files under `app/` stay intentionally thin:

- `app/layout.tsx` sets metadata, fonts, global CSS, and wraps everything with providers plus the shell
- `app/page.tsx` renders the inventory route
- `app/assets/[assetId]/page.tsx` renders the asset detail route
- `app/jobs/page.tsx` renders the jobs list
- `app/jobs/[jobId]/page.tsx` renders the job detail
- `app/replay/page.tsx` renders the replay workflow
- `app/visualize/page.tsx` redirects old replay links into `/replay`

Every page component uses `Suspense` and hands the real implementation to a route component in `components/`.

### App shell

`components/app-shell.tsx` owns the persistent chrome:

- header with logo and route navigation
- inventory and jobs tabs
- backend connectivity badge
- theme toggle
- centered max-width layout shared by every route

The shell keeps navigation intentionally light so pages remain the main surface.

### Providers

`components/app-providers.tsx` composes three global providers:

- `ThemeProvider` for light/dark/system theme control
- `SWRConfig` with `keepPreviousData`, no focus revalidation, and no automatic retries
- `FeedbackProvider` for toast-like alert messages

This means route components can assume consistent feedback handling and a shared SWR cache.

## Data Flow

### API layer

`lib/api.ts` is the single backend integration seam. It owns:

- frontend TypeScript types for backend responses and requests
- base URL resolution from `NEXT_PUBLIC_BACKEND_BASE_URL`
- a generic `request<T>` helper
- normalized backend error parsing through `BackendApiError`
- endpoint helpers for assets, tags, conversions, jobs, episodes, replay source, timeline, and samples

The API layer is intentionally thin and does not try to reshape backend responses into a different client model.

### SWR hooks

`hooks/use-backend.ts` wraps the API helper functions in SWR hooks and centralizes cache keys:

- `useHealth`
- `useAssets` and `useAsset`
- `useTags`
- `useJobs` and `useJob`
- `useConversions` and `useConversion`
- `useAssetEpisodes` and `useAssetEpisode`
- `useEpisodeViewerSource`
- `useEpisodeTimeline`
- `useEpisodeSamples`
- `usePrepareVisualization`
- `useBackendCache`

`useBackendCache` exists so route components can revalidate related surfaces together after a mutation without duplicating SWR key details.

### Polling model

There is no single global polling loop. Each surface starts polling only while it has active work:

- inventory polls while indexing is active or pending actions are in flight
- asset detail polls while indexing, jobs, or conversions are still active
- jobs list polls while any job is active
- job detail polls while the job or linked conversion is active
- replay polls viewer-source preparation and sample windows while playback or dragging is active

That keeps idle pages calm while still giving long-running backend jobs live feedback.

## Routing And URL State

The app relies heavily on URL state instead of hidden client-only state.

### Inventory route URL state

The inventory route stores filters and sorting in search params, including:

- `search`
- `tag`
- `type`
- `status`
- `min_duration`
- `max_duration`
- `size_min_mb`
- `size_max_mb`
- `registered_after`
- `registered_before`
- `sort`

This makes the inventory state shareable and lets detail pages return to the exact filtered list via `from=...`.

### Return navigation

`lib/navigation.ts` exposes `resolveReturnHref`, which only accepts local app paths. Asset detail, job detail, and replay routes use this to safely restore the prior page without trusting arbitrary external URLs.

### Replay route URL state

Replay keeps navigation and playback context in the URL:

- `asset_id`
- `episode_id`
- `from`
- `lanes`
- `speed`
- `timestamp_ns`

This makes the replay screen resumable and lets other pages link into a stable visualization context.

## Styling And Theming

### Global CSS

`app/globals.css` defines the design token layer:

- neutral shadcn-compatible color tokens
- light and dark variants
- radius scale
- chart/sidebar variables kept available for future growth
- mild color/border transitions when reduced motion is not requested

### Theme behavior

Theme support is split across two components:

- `components/theme-provider.tsx` wraps `next-themes` and adds a keyboard shortcut: pressing `d` toggles light/dark mode unless the user is typing in an input-like field
- `components/theme-toggle.tsx` renders the visible toggle in the header

Theme preference is stored under the key `hephaes-theme`.

## Shared Design System

The frontend uses shadcn-backed primitives in `components/ui/` as the default building blocks:

- `alert`
- `badge`
- `button`
- `card`
- `checkbox`
- `dialog`
- `input`
- `label`
- `native-select`
- `skeleton`
- `switch`
- `table`
- `textarea`

Most product-level components are shallow compositions of these primitives plus small helper badges and panels.

## Design Intent

The overall architecture follows a few steady rules:

- keep route files thin and put real behavior in components
- keep backend contracts explicit in one module
- let URL state represent shareable screen state
- favor small domain components over a large custom design system
- poll only while useful work is happening
- keep the app shell restrained so the data views stay primary
