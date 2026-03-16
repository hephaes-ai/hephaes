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
