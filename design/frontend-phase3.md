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

## Tasks

### API integration

- Extend the frontend API layer to support:
  - `POST /assets/{asset_id}/index`
  - `POST /assets/reindex-all`
  - updated `GET /assets/{asset_id}` metadata fields
- Add typed request and response helpers in [frontend/lib/api.ts](/Users/danielyoo/workspace/hephaes/frontend/lib/api.ts).
- Keep backend error parsing consistent so indexing failures surface as useful user-facing messages.
- Update the shared data-fetching hooks so asset list and asset detail queries can be invalidated or refetched after indexing actions.

### Inventory indexing actions

- Add a row-level index action to the inventory table.
- Add a retry affordance for failed assets directly from the inventory view.
- Add a bulk index action that operates on the current row selection.
- Keep these controls compact and shadcn-first, using existing button, badge, checkbox, and alert patterns instead of custom controls.
- Disable or guard actions while the relevant request is already in flight.

### Inventory state updates

- Reflect indexing state changes in the inventory without forcing a full page reload.
- Decide where optimistic updates are safe and where a refetch is clearer.
- Prevent duplicate submissions for assets already in `indexing`.
- Ensure row selection remains stable while indexing actions complete, unless the result set itself changes.
- Surface per-asset failures clearly when a bulk action partially succeeds.

### Asset detail page

- Replace the phase-1 placeholder metadata section with real indexed metadata from `GET /assets/{asset_id}`.
- Add clear sections for:
  - indexing status
  - last indexed time
  - duration and time bounds
  - topic count and message count
  - topic summaries
  - modality summaries
  - visualization readiness
- Add index and reindex actions on the detail page.
- Show useful empty states for assets that have not been indexed yet.
- Show useful failure states when metadata extraction failed.

### Metadata presentation

- Present topic and modality summaries in a compact, scannable format.
- Use shadcn cards, badges, alerts, separators, and button styles where suitable.
- Keep the visual treatment restrained so later phases can add playback and visualization tools without redesigning the page.
- Highlight whether an indexed asset has visualizable streams, but stop short of adding the actual viewer in this phase.

### Asynchronous workflow handling

- Decide how the frontend watches indexing progress after an action is triggered.
- Refetch or poll affected asset data while an asset is in `indexing`.
- Stop polling once the asset reaches `indexed` or `failed`.
- Make sure inventory and detail views stay consistent if indexing is triggered from either surface.

### Error and feedback UX

- Show success feedback when indexing completes successfully.
- Show clear error feedback for failed indexing runs.
- Distinguish between asset-not-found errors, validation errors, and indexing failures where possible.
- Keep feedback lightweight and consistent with the existing minimal app shell patterns.

### Navigation and state continuity

- Preserve inventory browsing context when navigating into an asset detail page and back.
- Ensure indexing actions do not unexpectedly clear search, filters, sort state, or selection state.
- Keep the phase-2 inventory browsing model intact while adding phase-3 actions.

### Local verification

- Run the frontend against the real local backend with phase 2 indexing support enabled.
- Confirm a user can trigger indexing from the inventory page.
- Confirm a user can trigger indexing or reindexing from the asset detail page.
- Confirm failed indexing runs surface visible retry affordances.
- Confirm indexed metadata appears correctly on the asset detail page after the backend finishes indexing.
- Confirm inventory and detail views stay in sync as asset statuses move through `pending`, `indexing`, `indexed`, and `failed`.
