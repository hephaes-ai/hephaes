# Frontend Phase 8A

## Goal

Establish visualization entry points and route foundations so users can navigate from inventory or asset detail into a stable visualization page shell.

## Depends On

- [frontend-phase8.md](frontend-phase8.md)
- [frontend-phase7.md](frontend-phase7.md)
- [backend-phase7.md](backend-phase7.md)
- [backend-phase8.md](backend-phase8.md)

## Scope

Implement:

- visualize entry actions from inventory and asset detail
- episode picker flow for multi-episode assets
- visualization route contract and URL-state basics
- API typing and hooks foundation for episode and viewer source discovery
- visualization page shell with loading, empty, and error states

## Tasks

### API and typing foundation

- Extend [frontend/lib/api.ts](../frontend/lib/api.ts) with typed support for:
  - GET /assets/{asset_id}/episodes
  - GET /assets/{asset_id}/episodes/{episode_id}
  - GET /assets/{asset_id}/episodes/{episode_id}/viewer-source
- Add core interfaces for:
  - episode summary and episode detail
  - viewer-source status payload
  - initial visualization metadata used by page header

### Server-state hooks

- Add SWR hooks in [frontend/hooks/use-backend.ts](../frontend/hooks/use-backend.ts) for:
  - episodes list by asset
  - single episode detail
  - viewer-source status by asset and episode
- Add cache helpers to revalidate episode and viewer-source state when navigation changes.

### Visualization entry points

- Add Visualize action to [frontend/components/inventory-page.tsx](../frontend/components/inventory-page.tsx).
- Add Visualize action to [frontend/components/asset-detail-page.tsx](../frontend/components/asset-detail-page.tsx).
- Only show/enable action when visualization-ready metadata exists.
- When multiple episodes are available, show an episode picker before route navigation.

### Routing and URL state baseline

- Add a dedicated route under [frontend/app](../frontend/app) for visualization.
- Standardize URL params for:
  - asset_id
  - episode_id
- Preserve return navigation context from inventory and asset detail.
- Ensure refresh and browser back/forward restore selected asset and episode.

### Visualization page shell

- Add a page shell component under [frontend/components](../frontend/components) with:
  - header (asset, episode, duration, stream counts)
  - placeholder transport row
  - placeholder scrubber area
  - placeholder viewer panel
  - placeholder inspector panel
- Use shadcn primitives and existing app-shell spacing and typography patterns.

### States and UX

- Implement loading, empty, unsupported, and backend-error states for initial visualization load.
- Keep light/dark theme behavior consistent with existing routes.

## Deliverable

By the end of phase 8A, a user can enter the visualization route from inventory/detail, choose an episode when needed, and land on a stable visualization shell with reliable route-state restoration.

## Verification

- verify visualize entry from inventory
- verify visualize entry from asset detail
- verify episode picker for multi-episode assets
- verify URL refresh and back/forward restoration
- run:
  - npm run lint
  - npm run typecheck
  - npm run build
