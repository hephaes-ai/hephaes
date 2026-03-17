# Frontend Phase 7

## Goal

Polish the local app state model and keep the frontend architecture open for saved searches, saved selections, and future dataset/query workflows.

## Depends On

- all prior frontend phases
- [backend-phase7.md](/Users/danielyoo/workspace/hephaes/design/backend-phase7.md)
- [frontend-ui-guidelines.md](/Users/danielyoo/workspace/hephaes/design/frontend-ui-guidelines.md)

## Product Scope

Strengthen:

- ingestion flexibility
- local state persistence
- navigation continuity
- empty, loading, and success feedback patterns
- future-ready information architecture

This phase is where the app should be made ready for:

- upload-based ingestion
- optional directory-scan ingestion
- visualization and playback workflows
- saved searches
- saved selections or collections
- dataset-building workflows
- query-driven workflows built on indexed assets

## Recommended State Strategy

Preserve and restore:

- active search term
- active filters
- selected sort order
- recent inventory view state when returning from detail pages
- recent visualization context when returning from detail pages or the visualization page
- theme preference

Recommended long-term state split:

- URL state for search, filters, sort, and view mode
- server-state cache for backend data
- app-level UI state for selection, dialogs, toasts, and jobs-panel visibility
- persistent local storage only for non-sensitive convenience state

## Ingestion Expansion

Once the backend supports richer ingestion, add frontend flows for:

- uploading one or more supported files
- showing upload progress or submission state
- optional local directory scanning
- clear duplicate handling during upload or scan-based registration

The frontend should keep path registration available for local power users if that still fits the product.

## UX Requirements

This phase should make the app resilient in everyday use.

Include:

- consistent loading indicators
- clear success and error messages
- duplicate-submission prevention
- theme consistency across light and dark mode
- strong empty states for:
  - no assets registered
  - no search results
  - no jobs yet
  - no metadata available yet

## Future-Ready Architecture Notes

Design the inventory and selection model so later actions can be launched from:

- all assets
- filtered results
- search results
- selected assets
- visualization-ready assets or episodes
- saved searches
- saved collections

The frontend should treat indexed assets as reusable inputs for later dataset and query features, not as one-off file records.

## Deliverable

By the end of phase 7, the frontend should:

- support both the long-term ingestion story and the core asset workflows cleanly
- preserve useful UI context during normal use
- feel coherent across inventory, detail, conversion, and jobs flows
- be ready for saved views and dataset-oriented workflows without major restructuring

## Tasks

### URL and navigation state

- Define a canonical URL state contract for inventory surfaces in [frontend/app/page.tsx](/Users/danielyoo/workspace/hephaes/frontend/app/page.tsx) and related components, including:
  - `search`
  - `status`
  - `tag`
  - sort field and sort direction
  - optional view mode if the inventory supports multiple layouts
- Ensure the inventory reads initial state from URL params and writes changes back to URL without full-page reloads.
- Preserve return-path behavior when navigating:
  - inventory -> asset detail -> inventory
  - inventory -> jobs -> job detail -> inventory
- Standardize `from` query parameter handling and guard against invalid or external redirect values.

### Persisted convenience state

- Add a lightweight persistence utility in [frontend/lib](../frontend/lib/) for non-sensitive preferences only.
- Persist and restore:
  - theme preference (if not already fully handled)
  - recent inventory presentation preferences not already represented in URL
  - optional jobs-panel visibility state (if panel mode is introduced later)
- Explicitly avoid persisting sensitive or backend-derived data.

### Ingestion workflow expansion

- Extend ingestion UI in [frontend/components/inventory-page.tsx](/Users/danielyoo/workspace/hephaes/frontend/components/inventory-page.tsx) to support multiple entry paths:
  - existing path registration
  - upload-based ingestion (when backend endpoint is available)
  - optional directory-scan ingestion (when backend endpoint is available)
- Add clear submission state and duplicate-submission prevention for each ingestion action.
- Add user-facing duplicate handling with explicit result messaging (registered, skipped duplicate, invalid).
- Keep local power-user path registration available as a first-class option.

### Inventory state model hardening

- Refactor inventory state ownership so concerns are explicit:
  - URL state for query/filter/sort/view
  - SWR server-state for backend entities
  - local UI state for transient controls (dialogs, checkboxes, pending actions)
- Add helper functions/selectors for future bulk actions based on scopes:
  - all assets
  - filtered assets
  - search results
  - selected assets
  - indexed or visualization-ready subsets
- Keep these selectors colocated with inventory logic to support future saved searches and collections.

### Shared feedback and request lifecycle patterns

- Normalize loading, success, and error surfaces across inventory, asset detail, jobs, and conversion flows.
- Reuse shadcn components for consistency:
  - `Alert`
  - `Skeleton`
  - `Badge`
  - `Button` disabled/loading states
- Ensure duplicate request prevention for:
  - ingestion submit
  - indexing trigger
  - conversion submit
  - tag mutations
- Add common helper utilities if repeated request-state logic appears across components.

### Empty-state quality pass

- Audit and unify empty-state content and hierarchy for:
  - no assets registered
  - no search results
  - no jobs yet
  - no metadata available
- Ensure empty states provide clear next actions (for example: register asset, clear filters, run indexing).
- Verify empty states remain legible and balanced in both light and dark themes.

### App shell and cross-surface coherence

- Review [frontend/components/app-shell.tsx](/Users/danielyoo/workspace/hephaes/frontend/components/app-shell.tsx) and route-level pages to ensure navigation continuity and active-state clarity.
- Keep interactions coherent between:
  - inventory
  - asset detail
  - jobs list
  - job detail
  - conversion entry points
- Confirm page-level loading fallbacks match the same visual language.

### Future-ready saved views scaffolding

- Introduce placeholder extension points (without implementing backend persistence yet) for:
  - saved searches
  - saved selections or collections
  - dataset-oriented action launchers
- Define TypeScript interfaces in [frontend/lib](../frontend/lib/) or [frontend/components](../frontend/components/) to model future saved-view entities and action scopes.
- Add non-blocking UI placeholders or disabled controls only where they improve discoverability without implying unsupported functionality.

### Verification and quality gates

- Add or update component-level tests for critical state and navigation behaviors where test infrastructure already exists.
- Manually verify:
  - URL state survives refresh and back/forward navigation
  - context is preserved when returning from detail pages
  - ingestion feedback and duplicate handling are clear
  - empty states match expected triggers
  - dark/light theme consistency on all updated surfaces
- Run frontend checks:
  - `npm run lint`
  - `npm run typecheck`
  - `npm run build`
