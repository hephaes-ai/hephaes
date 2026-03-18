# Outputs Page And Compute Actions

## Goal

Add a dedicated outputs workspace where users can find conversion artifacts, inspect their metadata, and launch output-scoped compute actions such as VLM tagging.

This page should become the artifact-centric companion to the current inventory, asset detail, and jobs views.

## Current Gaps

Right now conversion outputs are visible only as secondary details inside:

- the conversion dialog
- asset detail
- job detail

That makes outputs hard to rediscover later, hard to compare across runs, and awkward to use as the starting point for downstream compute.

## Product Shape

The frontend should treat outputs as their own top-level workflow surface, not as an afterthought attached to jobs.

Recommended route plan:

- phase 1: add `/outputs`
- phase 2: keep `/outputs` as the main workbench and optionally add `/outputs/[outputId]` only if the detail surface becomes too dense

Recommended shell change:

- add an `Outputs` tab to `components/app-shell.tsx`

## UX Principles

- Make finding outputs fast: search, filter, and sort should be first-class.
- Keep the page artifact-centric: rows represent output artifacts, not generic jobs.
- Preserve current app patterns: URL state, SWR hooks, restrained chrome, and status badges.
- Do not force users back through jobs or assets just to inspect an output they already know exists.
- Make compute actions feel like the next step from an output, not a separate hidden workflow.

## Proposed Page Structure

### Header

Show:

- page title
- total output count
- active action count when phase 2 lands
- refresh button

Short description:

- this page is the home for converted datasets and derived actions

### Filter Bar

Use URL-backed filters rather than hidden local state.

Recommended filters:

- `search`
- `format`
- `asset_id`
- `availability`
- `role`
- later: `action_type`
- later: `action_status`

Unlike the current jobs page, outputs should prefer server-backed filtering from the start because artifact counts can grow faster than job counts.

### Results Surface

Phase-1 default: a table on desktop with compact stacked rows on small screens.

Each row should show:

- output file name
- format
- source asset labels
- conversion creation time
- file size
- availability badge
- latest compute-action summary when present
- row actions

Recommended row actions:

- open detail panel
- download or open content URL
- copy local path
- jump to source asset
- jump to source job or conversion context
- later: run VLM tagging

### Detail Surface

Phase 1 can keep detail inline with a selected row or a side panel driven by a query param such as `output=<id>`.

Recommended detail contents:

- output identity
- source assets
- conversion config summary
- artifact path and content action
- manifest or schema summary
- related job or conversion links
- latest compute-action history once phase 2 lands

This keeps the initial implementation inside one page while still supporting shareable URLs.

## Frontend Data Model

Add frontend API types for:

- `OutputsQuery`
- `OutputSummary`
- `OutputDetail`
- `OutputActionSummary`
- `OutputActionDetail`
- `CreateOutputActionRequest`

Suggested query shape:

- `search`
- `format`
- `role`
- `asset_id`
- `conversion_id`
- `availability`
- `limit`
- `offset`

## Hook And Cache Plan

Extend `frontend/lib/api.ts` with:

- `listOutputs()`
- `getOutput()`
- `listOutputActions()`
- `createOutputAction()`
- `getOutputAction()`

Extend `frontend/hooks/use-backend.ts` with:

- `useOutputs(query)`
- `useOutput(outputId)`
- `useOutputActions(outputId)`
- `useOutputAction(actionId)` if needed

Extend `useBackendCache()` with:

- `revalidateOutputs()`
- `revalidateOutputDetail(outputId)`
- `revalidateOutputActions(outputId)`

## Integration Points With Existing Screens

The outputs page should not replace the current entry points, but it should become the best follow-up destination from them.

Recommended links:

- conversion dialog: `View outputs`
- job detail: jump to `/outputs?conversion_id=...`
- asset detail: jump to `/outputs?asset_id=...`

That keeps the current flows useful while making outputs discoverable later.

## Polling Strategy

Phase 1 can stay mostly manual-refresh because the page lists completed artifacts rather than active conversions.

Phase 2 should poll only while any output action is `queued` or `running`.

That follows the same local, on-demand polling pattern already used elsewhere in the app.

## Compute Action UX

### Phase-2 first action: VLM tagging

Recommended interaction:

1. user opens an output
2. user clicks `Run VLM tagging`
3. dialog asks for a small config
4. submission creates a durable action record
5. output row and detail panel show live status plus final result summary

Recommended first-pass config fields:

- target field or image-bearing column
- prompt template
- sample cap
- overwrite toggle

### Result display

Keep result display small at first.

Show:

- action status badge
- created and finished time
- short result summary
- link to result artifact or JSON

Avoid building a full annotation editor in the first implementation.

## Phased Approach

### Phase 1: Outputs Explorer

Frontend work:

- add `/outputs` route and route component
- add `Outputs` navigation tab
- add API types and hooks for list/detail
- implement URL-backed search and filters
- render table or stacked list for all outputs
- add a light detail panel driven by selected output ID
- add links from job detail, asset detail, and conversion dialog into the new page

Exit criteria:

- a user can find any converted output from one page
- the page is shareable via URL filters
- users can inspect output metadata and open the artifact without revisiting the original job

### Phase 2: First Output Compute Action

Frontend work:

- add output action API bindings and cache revalidation
- add `Run VLM tagging` entry point in row actions and output detail
- add action history to the detail panel
- poll while action status is active
- surface latest action summary on list rows

Exit criteria:

- a user can launch and monitor VLM tagging from the outputs page
- refreshes preserve action visibility and status
- outputs page becomes the default home for output-scoped compute

### Phase 3: Richer Preview And Batch Workflows

Frontend work:

- add richer preview widgets for Parquet and TFRecord-backed outputs
- support multi-select plus batch compute actions
- support saved or prefilled filter states for common output slices
- consider a dedicated `/outputs/[outputId]` route if the detail surface outgrows the single-page layout

Exit criteria:

- outputs page supports both discovery and deeper inspection
- users can operate on multiple outputs without repetitive single-item flows
- the route structure still feels consistent with the rest of the app
