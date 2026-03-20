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

## Current Status

Phase 1 is complete in the frontend.

The current implementation ships:

- `app/dashboard/page.tsx`
- `components/dashboard-page.tsx`
- `lib/dashboard.ts`
- a `Dashboard` nav entry in `components/app-shell.tsx`

The route currently aggregates `useAssets()`, `useJobs()`, `useConversions()`, and `useOutputs()` in the browser, then leans on the refactored shared frontend seams such as:

- `components/empty-state.tsx`
- `lib/format.ts`
- `lib/navigation.ts`
- `lib/outputs.ts`

That means frontend phase 2 should be a data-source swap plus a small contract cleanup, not another route redesign.

## Current Frontend Seams

After the recent frontend refactor, the main dashboard seams are:

- `app/dashboard/page.tsx`
- `components/dashboard-page.tsx`
- `hooks/use-backend.ts`
- `lib/api.ts`
- `lib/dashboard.ts`
- `lib/navigation.ts`
- `lib/outputs.ts`
- `components/app-shell.tsx`
- `components/empty-state.tsx`

Relevant read hooks already exist:

- `useAssets()`
- `useJobs()`
- `useConversions()`
- `useOutputs()`
- `useOutputActions()`

That is how phase 1 shipped, and it also means phase 2 can stay focused on backend-owned contracts rather than frontend structure.

## Recommended Phases

### Cross-Package Dependency Order

The intended dashboard rollout across packages is:

1. `hephaes` phase 1
2. `frontend` phase 1 and `backend` phase 1
3. `backend` phase 2
4. `frontend` phase 2
5. `hephaes` phase 2
6. `hephaes` phase 3
7. `backend` phase 3
8. `frontend` phase 3
9. `hephaes` phase 4
10. `backend` phase 4 only if live aggregation proves too slow

### Phase 1: Client-Aggregated Operations Dashboard

Status:

- complete
- the live page still labels itself as `Phase 1 client aggregation`

Goal:

- ship a useful dashboard without waiting on new backend endpoints

Dependencies:

- this phase depends only on the existing backend read APIs plus the small stability/testing work described in backend phase 1
- this phase does not require backend phase 2 or any new `hephaes` work beyond the current baseline

Implemented route and files:

- `app/dashboard/page.tsx`
- `components/dashboard-page.tsx`
- `lib/dashboard.ts`
- `components/app-shell.tsx`

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

Current implementation notes:

- phase-1 aggregation stays inside the frontend for small to moderate local datasets
- the page intentionally avoids fan-out asset detail reads and works from existing list routes only
- drill-down links already flow through the refactored shared navigation helpers instead of page-local URL builders

Exit criteria:

- the dashboard loads using existing APIs only
- loading, empty, and degraded states are clear
- the page answers "what landed, what is blocked, what is ready"

### Phase 2: Adopt Backend Summary Endpoints

Goal:

- move heavy aggregation out of the browser and make the dashboard scale with larger inventories

Dependencies:

- this phase depends directly on backend phase 2 landing `GET /dashboard/summary` and `GET /dashboard/trends`
- this phase can preserve the phase-1 visual layout because the dependency change is in the data contract, not the page structure
- the `hephaes` phase-1 dependency is already satisfied upstream

Frontend work:

- add dashboard response types plus `getDashboardSummary()` and `getDashboardTrends()` to `lib/api.ts`
- add `backendKeys.dashboardSummary`, `backendKeys.dashboardTrends`, `useDashboardSummary()`, and `useDashboardTrends()` to `hooks/use-backend.ts`
- replace the `useAssets()` / `useJobs()` / `useConversions()` / `useOutputs()` dashboard fetch pattern in `components/dashboard-page.tsx` with the new summary hooks
- keep the existing cards, trend panels, empty state, partial-data alert, and drill-down links so the route does not need a redesign
- remove or repurpose the current `Phase 1 client aggregation` badge once the page is backed by server summaries
- trim `lib/dashboard.ts` down to UI-only helpers such as trend shaping or recent-failure presentation if the heavy reducers become redundant

Frontend phase-2 implementation checklist:

- [x] document the concrete frontend phase-2 task list and execution order
- [x] add dashboard summary and trends response types plus fetch helpers to `frontend/lib/api.ts`
- [x] add `backendKeys.dashboardSummary`, `backendKeys.dashboardTrends`, `useDashboardSummary()`, and `useDashboardTrends()` to `frontend/hooks/use-backend.ts`
- [x] refactor `frontend/components/dashboard-page.tsx` so cards, counts, and charts read from backend summary contracts instead of client-side asset and output aggregation
- [x] preserve the existing empty state, partial-data alert, drill-down links, and recent-failures table while limiting list-based reads to UI that still needs record-level detail
- [x] repurpose the current phase badge and description to reflect backend-owned dashboard rollups
- [x] trim `frontend/lib/dashboard.ts` to UI-only shaping helpers that still serve the page after the summary swap
- [x] run frontend validation for the changed files

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

Dependencies:

- this phase depends on backend phase 3 quality and readiness rollups, which themselves depend on `hephaes` phase 2 and phase 3
- this phase should start only after the backend-owned contracts and drill-down targets are stable enough to support deeper readiness UX

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
- `lib/navigation.ts`
- `lib/outputs.ts`
- optionally `components/ui/card.tsx` consumers for metric cards and trend panels

## Testing Plan

- keep unit coverage for any UI-only helpers that remain in `lib/dashboard.ts`
- add hook coverage for `useDashboardSummary()` and `useDashboardTrends()` once they land
- add component-level coverage for empty, loading, and partial-data states
- verify URL-driven drill-down links into `/`, `/jobs`, and `/outputs`
- add at least one regression test that verifies the backend summary payload reproduces the same mixed-status totals the phase-1 dashboard already shows

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
