# Frontend Phase 6

## Goal

Make jobs and outputs first-class UI concepts so indexing and conversion workflows are transparent and inspectable.

## Depends On

- [backend-phase5.md](/Users/danielyoo/workspace/hephaes/design/backend-phase5.md)
- [backend-phase6.md](/Users/danielyoo/workspace/hephaes/design/backend-phase6.md)
- [backend-phase7.md](/Users/danielyoo/workspace/hephaes/design/backend-phase7.md) for richer asset detail aggregation
- [frontend-ui-guidelines.md](/Users/danielyoo/workspace/hephaes/design/frontend-ui-guidelines.md)

## Product Scope

Implement:

- a jobs page or jobs panel
- job list with type, status, and creation time
- job detail view or drawer
- polling-based status refresh
- error display for failed jobs
- output display for completed conversions
- links from jobs back to related assets
- conversion history on the asset detail page

Jobs and output views should remain clean and operationally focused. Prefer shadcn tables, badges, drawers, alerts, and tabs over bespoke dashboard styling.

## Recommended UI Surfaces

### Jobs page

- job table or list
- status badges
- created-at and updated-at timestamps
- filters by job type and status if useful

### Job detail

- job type
- target assets
- current status
- error information
- output path and output metadata

### Asset detail page

- related jobs section
- conversion history section

## State and Data Guidance

Recommended behavior:

- poll job data on an interval while active jobs exist
- reduce or stop polling when no jobs are active
- keep job detail navigation lightweight so users can move between jobs and source assets easily

## Backend Endpoints Used

- `GET /jobs`
- `GET /jobs/{job_id}`
- `GET /conversions`
- `GET /conversions/{conversion_id}`
- `GET /assets/{asset_id}`

## Deliverable

By the end of phase 6, a user should be able to:

- monitor indexing and conversion jobs without refreshing the app
- inspect failures and outputs
- move between job views, assets, and conversion results cleanly

## Tasks

### API integration

- Extend the frontend API layer in [frontend/lib/api.ts](/Users/danielyoo/workspace/hephaes/frontend/lib/api.ts) with typed support for:
  - `GET /jobs`
  - `GET /jobs/{job_id}`
- Update existing asset and conversion response types so the frontend can consume:
  - `related_jobs` from `GET /assets/{asset_id}`
  - conversion history from `GET /assets/{asset_id}`
  - conversion detail output fields from `GET /conversions/{conversion_id}`
- Normalize job and conversion status handling so badges, polling logic, and failure states can be shared across surfaces.

### Server-state hooks

- Add SWR hooks in [frontend/hooks/use-backend.ts](/Users/danielyoo/workspace/hephaes/frontend/hooks/use-backend.ts) for:
  - jobs list
  - single job detail
  - conversions list if phase 5 did not already expose the needed cache behavior
- Add cache revalidation helpers so indexing and conversion actions can refresh:
  - jobs views
  - asset detail related-jobs panels
  - conversion history panels
- Keep polling scoped to active jobs so the UI stays responsive without polling finished histories unnecessarily.

### Shared jobs UI

- Add reusable shadcn-first UI pieces for job status and job detail presentation, such as:
  - status badges
  - compact metadata rows
  - error alerts
  - output-path and output-file lists
- Keep the visual treatment minimal and operational rather than dashboard-heavy.

### Jobs page or panel

- Add a dedicated jobs surface, either:
  - a `/jobs` page
  - or a persistent jobs panel if that fits the app shell better
- Render a jobs table or list with at least:
  - job type
  - status
  - created time
  - updated time
  - target asset count
- Add lightweight empty, loading, and error states for the jobs surface.

### Job detail surface

- Implement a job detail view or drawer that shows:
  - job type
  - current status
  - target asset links
  - timestamps
  - error message when failed
  - output path when available
- Keep navigation lightweight so users can move back to the jobs list or into related asset detail pages without losing context.

### Asset detail integration

- Extend [frontend/components/asset-detail-page.tsx](/Users/danielyoo/workspace/hephaes/frontend/components/asset-detail-page.tsx) to render:
  - a related jobs section
  - a conversion history section
- Reuse the same status and detail primitives used on the jobs surface.
- Add links from each related job or conversion back into the dedicated job or conversion detail view if phase 6 introduces one.

### Polling and status handoff

- Poll jobs data on an interval only while queued or running jobs are present.
- Reflect job completion cleanly in:
  - the jobs page or panel
  - asset detail related jobs
  - conversion history
- Keep success handling quiet and readable, while preserving clear failed-state alerts.

### Output display

- Show conversion outputs in a compact, inspectable way, including:
  - output path
  - output files
  - linked conversion status
- Make sure completed conversion jobs and conversion-history entries surface the same output information consistently.

### Navigation and UX polish

- Add an app-shell navigation entry for the jobs surface if phase 6 uses a dedicated page.
- Preserve context when moving between:
  - jobs
  - assets
  - conversions
- Keep the UI aligned with the minimal shadcn-first design guidance and dark-mode behavior already established in earlier phases.

### Local verification

- Verify the jobs list updates while indexing or conversion work is running.
- Verify failed jobs surface error details clearly.
- Verify completed conversions show output metadata in both jobs and asset detail contexts.
- Run:
  - `npm run lint`
  - `npm run typecheck`
  - `npm run build`
