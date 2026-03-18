# Inventory And Assets

## Inventory Route

`components/inventory-page.tsx` is the largest surface in the frontend and acts as the operational home screen for the product.

It combines:

- asset ingestion
- server-backed search and filtering
- local refinements and sorting
- asset selection and bulk actions
- tag management for selections
- conversion launch for selections
- per-row indexing and replay entry points

## Inventory Data Model

The page intentionally uses two levels of filtering.

### Server-backed filters

The `AssetListQuery` sent through `useAssets()` covers fields the backend can filter directly:

- `search`
- `status`
- `tag`
- `type`
- `min_duration`
- `max_duration`

### Local-only refinements

The page then refines the fetched results in the client for:

- minimum and maximum file size
- registered-after and registered-before date boundaries
- table sort order

This gives the page richer filtering today without forcing the backend contract to grow in lockstep.

## URL-State Contract

The inventory page is built around `useSearchParams()` and updates the URL through `router.replace()` rather than storing filter state in hidden local state.

Important effects of that decision:

- filtered views are shareable
- navigating to detail pages can preserve the current inventory state in `from`
- the search and filter drawer reopens automatically when query params are present
- future saved-search workflows can reuse the existing URL contract

## Ingestion Flows

The inventory route currently exposes two ingestion flows directly from the UI.

### File upload

The hidden file input supports `.bag` and `.mcap` uploads. The page uploads files one by one with `uploadAssetFile()` so it can:

- track progress as `completed/total`
- classify duplicates and invalid files as skipped items
- surface partial-success messaging instead of collapsing everything into a single failure

### Directory scan

The directory scan dialog submits `directory_path` plus a `recursive` flag through `scanDirectoryForAssets()`.

The result handling is structured to distinguish:

- files discovered
- files newly registered
- duplicates and invalid paths skipped
- scans that find no supported files at all

The dialog resets on close and blocks closing while an active scan is in flight.

## Inventory Table

The inventory table is rendered by the internal `AssetsTable` component and keeps the table itself focused on display and row interaction.

Each row includes:

- selection checkbox
- file name and source path
- tags
- file type
- file size
- indexing status badge
- registration time
- last indexed time
- row actions for replay and indexing

Interaction rules:

- clicking a row opens asset detail
- click targets inside `data-stop-row-click="true"` do not trigger row navigation
- keyboard `Enter` and space also open the row

## Selection And Bulk Workflows

Selection is limited to currently visible assets and is automatically trimmed when filters change.

Bulk behaviors currently implemented:

- bulk selection for visible rows
- bulk indexing for selected assets
- bulk conversion launch for selected visible assets
- bulk tag application or tag creation for the selection
- clear selection

The page also computes a lightweight `selectionScope` value using `lib/future-workflows.ts` so future saved-selection and dataset workflows can reuse the same semantics.

## Indexing Behavior

There are three indexing entry points from inventory:

- per-row index or reindex
- bulk index selected
- index all pending or failed assets via `reindexAllAssets()`

Implementation notes:

- pending row actions are tracked in a local `Set<string>` of asset IDs
- bulk indexing runs sequentially and reports partial failures cleanly
- the page polls while indexing is active so statuses settle without manual refresh

## Tags In Inventory

Tag support on the inventory page has two roles.

### Filter tags

Tags with at least one asset are loaded through `useTags()` and exposed as a filter select. If an active tag is present but currently has zero assets, it is still preserved in the filter options so the page can render the current URL state faithfully.

### Bulk tag editing

When assets are selected, the page shows `TagActionPanel` so the user can:

- apply an existing tag to all selected visible assets
- create a new tag and then apply it

Duplicate tag applications are skipped rather than treated as failures.

## Future Workflow Placeholders

The inventory page includes small placeholder buttons for:

- saved searches
- saved selections

These do not mutate data yet. They deliberately preserve the future workflow seams without pretending the features already exist.

## Asset Detail Route

`components/asset-detail-page.tsx` is the deep-inspection page for a single asset.

It combines:

- top-level asset identity and status
- indexing actions
- tag editing
- conversion launch
- replay launch
- indexed metadata
- related jobs
- conversion history
- topic summaries

## Navigation Model

Asset detail resolves its back link from the `from` query param using `resolveReturnHref()`. That keeps users anchored to the filtered inventory or jobs context they came from.

The page also builds a `currentDetailHref` value and passes it to downstream job and replay links so second-level navigation can return to the same asset detail state.

## Detail Polling

Asset detail polls every 1.5 seconds while any of these are true:

- the asset is indexing
- a related job is queued or running
- a related conversion is queued or running

While polling, it refreshes:

- the asset detail itself
- asset lists
- jobs
- conversions

This keeps the detail view live without requiring a global realtime layer.

## Asset Detail Sections

### Header actions

The header exposes the asset status plus contextual actions:

- replay when indexed metadata reports visualizable streams and at least one episode
- convert
- index, retry, or reindex

### Status notices

Inline notices explain the current indexing state:

- not yet indexed
- indexing in progress
- last run failed

### Asset details

This is the registry-level metadata returned even before indexing completes:

- file type
- file size
- registration time
- last indexed time
- asset ID

### Tags

The asset detail page supports the full lifecycle:

- view tags
- remove tags inline from badges
- attach existing tags
- create new tags and attach immediately

### Indexed metadata

When indexing has succeeded, the page shows:

- duration
- default episode
- start and end time
- topic count
- message count
- visualization readiness
- lane count
- sensor types
- modality mix
- raw metadata badges

If indexing is pending, running, or failed, the page swaps this section into a matching empty-state explanation instead of leaving a blank card.

### Related jobs

The page surfaces recent backend work linked to the asset, including:

- job type
- job ID
- status
- created and updated timestamps
- output path
- error message
- direct navigation to the job detail page

### Conversion history

Asset detail also surfaces recent conversions tied to the asset and lets the user jump into the underlying job for deeper inspection.

### Topic summary

Indexed topic data is shown in a table with:

- topic name
- message type
- message count
- rate
- modality

The section also highlights replay readiness and lane count through a badge tied to `visualization_summary`.

## Shared Components Used Most Heavily Here

Inventory and asset detail rely on the same small set of domain components:

- `AssetStatusBadge`
- `TagBadgeList`
- `TagActionPanel`
- `ConversionDialog`
- `WorkflowStatusBadge`
- `FormNotice` and inline alert patterns

That gives the high-traffic asset flows a consistent vocabulary for state, actions, and feedback.
