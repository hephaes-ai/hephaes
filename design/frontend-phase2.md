# Frontend Phase 2

## Goal

Turn the inventory page into a practical browsing tool with search, filtering, sorting, and stable inventory state.

## Depends On

- [backend-phase1.md](/Users/danielyoo/workspace/hephaes/design/backend-phase1.md)
- [backend-phase3.md](/Users/danielyoo/workspace/hephaes/design/backend-phase3.md) for richer filtering support
- [frontend-ui-guidelines.md](/Users/danielyoo/workspace/hephaes/design/frontend-ui-guidelines.md)

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

Continue using shadcn components for search, filter, sort, and selection controls wherever suitable, and keep the browsing UI compact and visually quiet.

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

## Tasks

### Inventory state model

- Refactor the inventory page state so search, filters, sort, and pagination can be managed independently from the table rendering.
- Move durable browsing state into the URL where practical so the inventory view can be shared, refreshed, and revisited without losing context.
- Keep temporary UI state such as open popovers, drawers, and row selection local to the page.
- Preserve inventory browsing state when navigating from the inventory to an asset detail page and back.

### Search and filter controls

- Add a compact search input for file-name search.
- Prefer shadcn input, select, popover, drawer, command, badge, and button primitives wherever a suitable control already exists.
- Add controls for:
  - file type
  - indexing status
  - file size range
  - date added
  - duration when available
- Make filters easy to clear individually and all at once.
- Show active filter chips or an equivalent compact summary of the current filter state.
- Keep the controls visually quiet and minimal so the table remains the primary surface.
- Design duration and metadata-backed filters so they can be disabled or hidden cleanly until backend support is available.

### Sorting behavior

- Add sorting controls for file name, date added, file size, and duration when available.
- Support ascending and descending order.
- Make the active sort state visible without adding heavy visual chrome.
- Ensure sort state stays synchronized with URL state and data fetching.

### Inventory results table

- Keep the registered assets table as the main content area of the page.
- Extend the table layout to support search, filtering, and sorting without becoming visually crowded.
- Use stable shadcn table, checkbox, badge, skeleton, empty-state, and dropdown primitives where possible instead of custom foundations.
- Add a no-results state that distinguishes filtered-empty from truly empty inventory.
- Add pagination, lazy loading, or virtualization if needed once the data volume justifies it.

### Selection groundwork

- Add row selection checkboxes.
- Add a select-all mechanism scoped to the current result set or page.
- Show a lightweight selected-count indicator.
- Structure the selection state so later phases can attach bulk actions without redesigning the inventory view.
- Keep selection affordances subtle and consistent with the minimal UI direction.

### Data integration

- Continue fetching inventory data from `GET /assets`.
- Implement client-side search, filter, and sort behavior first if backend query support is not yet available.
- Avoid coupling the UI too tightly to client-only filtering so server-side query support can replace it later without a rewrite.
- Keep the asset list query/cache layer separate from presentational components.

### Navigation and UX polish

- Ensure returning from an asset detail page restores the user’s inventory browsing context.
- Keep loading, empty, and no-results states clean and low-noise.
- Make control spacing and density feel intentional and uncluttered in both light and dark themes.
- Continue following the shared frontend UI guidelines so phase 2 remains shadcn-first and visually restrained.

### Local verification

- Run the frontend against the real local backend.
- Confirm search by file name works on the registered asset list.
- Confirm each supported filter can be applied and cleared.
- Confirm sorting updates the visible result order correctly.
- Confirm inventory state survives navigation to an asset detail page and back.
- Confirm the table remains the dominant page surface and the controls stay compact in both light and dark mode.
