# Frontend Phase 3

## Goal

Add indexing workflows and a more useful asset detail experience once backend metadata persistence exists.

## Depends On

- [backend-phase2.md](/Users/danielyoo/workspace/hephaes/design/backend-phase2.md)
- [frontend-ui-guidelines.md](/Users/danielyoo/workspace/hephaes/design/frontend-ui-guidelines.md)

## Product Scope

Implement:

- index action for a single asset
- bulk index action for selected assets
- retry action for failed assets
- status badges for unindexed, indexing, indexed, and failed assets
- metadata sections in the asset detail view
- topic and modality summaries in the asset detail view
- visualization availability indicators for indexed assets when supported streams exist
- user-visible indexing errors

## Recommended UI Surfaces

### Inventory page

- row-level index action
- bulk index action in the selection toolbar
- clear status badges and retry affordances

### Asset detail page

- base file information
- indexing status and last indexing time
- extracted metadata panels
- topic and modality summary sections when available
- visualization readiness summary when the backend reports visualizable streams
- index and reindex actions

## State and Data Guidance

The frontend should handle indexing as an asynchronous workflow.

Recommended behavior:

- submit index requests optimistically only where safe
- refetch or poll affected asset data while indexing is in progress
- surface per-asset failures clearly
- avoid duplicate submissions while an indexing request is already in flight
- continue using minimal shadcn-based status, badge, button, and alert patterns instead of custom visual treatments

## Backend Endpoints Used

- `POST /assets/{asset_id}/index`
- `POST /assets/reindex-all`
- `GET /assets`
- `GET /assets/{asset_id}`

## Deliverable

By the end of phase 3, a user should be able to:

- trigger indexing from inventory or detail views
- see indexing progress reflected in the UI
- inspect extracted metadata and indexed topic summaries on the detail page
- retry failed indexing runs
