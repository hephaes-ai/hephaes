# Frontend Phase 7

## Goal

Polish the local app state model and keep the frontend architecture open for saved searches, saved selections, and future dataset/query workflows.

## Depends On

- all prior frontend phases
- [backend-phase7.md](/Users/danielyoo/workspace/hephaes/design/backend-phase7.md)

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
- saved searches
- saved collections

The frontend should treat indexed assets as reusable inputs for later dataset and query features, not as one-off file records.

## Deliverable

By the end of phase 7, the frontend should:

- support both the long-term ingestion story and the core asset workflows cleanly
- preserve useful UI context during normal use
- feel coherent across inventory, detail, conversion, and jobs flows
- be ready for saved views and dataset-oriented workflows without major restructuring
