# Dashboard Phased Implementation

## Summary

Yes, a dashboard is implementable from the repo's current state.

The important caveat is that the current stack supports a good operational dashboard immediately, but not every robotics-specific quality metric without additional backend and `hephaes` work.

Today the frontend already has read paths for:

- assets
- jobs
- conversions
- outputs
- output actions

That is enough to ship a first dashboard focused on:

- inventory volume
- ingest and indexing backlog
- recent job health
- conversion health
- output catalog growth

The current stack is not yet ideal for metrics that depend on per-asset indexed metadata at list scale, such as:

- total recorded hours across all indexed assets
- modality coverage across the fleet
- missing sensor combinations
- per-robot or per-site quality rollups

Those should be phased in after backend summary APIs and richer `hephaes` extraction land.

## Current Frontend Seams

Existing hooks and contracts already line up with a dashboard surface:

- `hooks/use-backend.ts`
- `lib/api.ts`
- `components/app-shell.tsx`

Relevant read hooks already exist:

- `useAssets()`
- `useJobs()`
- `useConversions()`
- `useOutputs()`
- `useOutputActions()`

That means phase 1 can be a new route plus aggregation logic, not a frontend architecture rewrite.

## Recommended Phases

### Phase 1: Client-Aggregated Operations Dashboard

Goal:

- ship a useful dashboard without waiting on new backend endpoints

Recommended route and files:

- add `app/dashboard/page.tsx`
- add `components/dashboard-page.tsx`
- add dashboard-specific aggregation helpers under `lib/dashboard.ts`
- add a `Dashboard` nav entry in `components/app-shell.tsx`

Recommended phase-1 cards and charts:

- total assets
- total storage bytes from `AssetSummary.file_size`
- new assets in last 7 and 30 days from `registered_time`
- indexing status counts from `indexing_status`
- queued and running jobs
- failed jobs in last 24 hours
- conversions by status
- output artifact count and total output bytes
- outputs by format
- recent failures table sourced from jobs and conversions

Recommended data sources:

- `useAssets()` for counts, storage, ingest trend, indexing backlog
- `useJobs()` for queue depth, recent failures, active work
- `useConversions()` for conversion throughput and success/failure ratios
- `useOutputs()` for output growth, format mix, output availability

Implementation note:

- keep phase-1 aggregation inside the frontend for small to moderate local datasets
- avoid fan-out fetching every asset detail just to compute deeper metrics
- if a duration-based or modality-based card is desired before backend work lands, gate it behind a capped detail fetch and label it as approximate

Exit criteria:

- the dashboard loads using existing APIs only
- loading, empty, and degraded states are clear
- the page answers "what landed, what is blocked, what is ready"

### Phase 2: Adopt Backend Summary Endpoints

Goal:

- move heavy aggregation out of the browser and make the dashboard scale with larger inventories

Frontend work:

- add `getDashboardSummary()` and `getDashboardTrends()` to `lib/api.ts`
- add `useDashboardSummary()` and `useDashboardTrends()` to `hooks/use-backend.ts`
- replace client-side reducers with server-provided rollups
- preserve the same visual layout so the route does not need a redesign

Metrics to unlock cleanly in this phase:

- total indexed duration
- message-count rollups
- sensor-type distribution
- output row-count rollups from output metadata
- time-series trends without loading every row into the client

Exit criteria:

- the dashboard remains fast as asset and output counts grow
- page load does not require fetching the full inventory just to render summary cards
- chart buckets and summary totals come from backend-owned contracts

### Phase 3: Robotics Data Quality And ML Readiness

Goal:

- graduate from an operations dashboard into a true robotics data-readiness dashboard

Frontend additions once backend and `hephaes` expose richer fields:

- modality completeness matrix
- missing required metadata count
- per-robot and per-site coverage
- logs convertible now vs blocked
- training-ready dataset hours
- manifest coverage and label coverage
- quality warnings and top blockers

Recommended UX:

- keep the landing view summary-first
- add drill-down links into filtered inventory, jobs, and outputs pages
- avoid turning the dashboard into a separate workflow surface with duplicate tables

Exit criteria:

- users can move from a red metric directly into the filtered records that caused it
- the dashboard reflects both operational health and ML readiness

## File-Level Implementation Notes

Likely frontend files to touch over time:

- `app/dashboard/page.tsx`
- `components/dashboard-page.tsx`
- `components/app-shell.tsx`
- `hooks/use-backend.ts`
- `lib/api.ts`
- `lib/dashboard.ts`
- optionally `components/ui/card.tsx` consumers for metric cards and trend panels

## Testing Plan

- add unit coverage for aggregation helpers in `lib/dashboard.ts`
- add component-level coverage for empty, loading, and partial-data states
- verify URL-driven drill-down links into `/`, `/jobs`, and `/outputs`
- add at least one regression test for mixed-status data so failed and active work are counted correctly

## Suggested First Slice

If only one slice ships first, make it operational rather than aspirational:

- inventory count
- total storage
- new logs this week
- indexed vs pending vs failed
- active jobs
- failed jobs
- conversions succeeded vs failed
- outputs created this week

That slice is already supported by the repo with no backend schema changes.
