# Frontend Overview

## Docs In This Directory

- [architecture.md](./architecture.md): stack, app shell, providers, routing model, styling, and data flow
- [inventory-and-assets.md](./inventory-and-assets.md): inventory route, asset detail route, indexing, tagging, filtering, and conversion entry points
- [jobs-and-conversions.md](./jobs-and-conversions.md): jobs list/detail flows and the conversion workflow
- [outputs-page-and-compute-actions.md](./outputs-page-and-compute-actions.md): phased plan for a dedicated outputs workspace and output-scoped compute actions
- [replay-and-visualization.md](./replay-and-visualization.md): replay route, timeline/scrubber behavior, viewer-source preparation, and Rerun integration state
- [shared-components-and-utils.md](./shared-components-and-utils.md): shared domain components, hooks, API helpers, utility modules, and UI primitives
- [frontend-ui-guidelines.md](./frontend-ui-guidelines.md): canonical UI guidance that used to live under the repository root `design/`

## Current Route Map

- `/`: inventory, ingestion, filtering, tagging, bulk actions, and conversion launch
- `/assets/[assetId]`: asset detail, indexed metadata, tag editing, related jobs, conversion history, and replay launch
- `/jobs`: durable backend job history with type/status filtering
- `/jobs/[jobId]`: job detail plus linked conversion output and asset navigation
- `/replay`: replay and visualization shell
- `/visualize`: compatibility redirect into `/replay`

## Code Map

- `app/`: App Router entrypoints and layout shell
- `components/`: route-level components and shared domain UI
- `components/ui/`: shadcn/Radix-backed primitives used throughout the app
- `hooks/use-backend.ts`: SWR hooks and cache revalidation helpers
- `lib/api.ts`: backend contracts and request helpers
- `lib/`: formatting, navigation, replay URL helpers, and placeholder future-workflow types
