# Frontend Phase 2

## Goal

Turn the inventory page into a practical browsing tool with search, filtering, sorting, and stable inventory state.

## Depends On

- [backend-phase1.md](/Users/danielyoo/workspace/hephaes/design/backend-phase1.md)
- [backend-phase3.md](/Users/danielyoo/workspace/hephaes/design/backend-phase3.md) for richer filtering support

## Product Scope

Expand the inventory view to support:

- search by file name
- metadata-backed search when indexed fields become available
- filter by file type
- filter by indexing status
- filter by file size range
- filter by date added
- filter by duration when available
- sort by file name
- sort by date added
- sort by file size
- sort by duration when available
- selection groundwork for future bulk actions

Duration and tag filters should be designed into the UI, but they can remain disabled or hidden until the backend supports them.

## Recommended UI Surfaces

### Inventory controls

- search input with clear action
- filter panel, drawer, or inline controls
- active filter chips
- sort control with ascending and descending support
- selection checkboxes on list rows
- selected-count indicator

### Inventory results

- stable table or grid layout
- pagination, lazy loading, or virtualization for large result sets
- loading skeletons
- no-results state
- no-assets state

## State and Data Guidance

This phase should establish the long-term inventory state model.

Recommended state split:

- URL state for search, filters, and sort
- query/cache state for fetched asset lists
- local state for row selection and temporary UI controls

Preserve search, filter, and sort state while navigating between the inventory and asset detail page.

## Backend Endpoints Used

- `GET /assets`

Query support should evolve as backend search and filter support grows. The frontend should not hardcode assumptions that every filter is available on day one.

## Deliverable

By the end of phase 2, a user should be able to:

- search assets by name
- use metadata-driven search once indexed fields are available
- apply and clear multiple filters
- sort inventory results
- keep inventory state while navigating within the app
- prepare selected assets for later bulk workflows
