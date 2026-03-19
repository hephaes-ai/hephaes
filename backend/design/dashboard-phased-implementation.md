# Dashboard Phased Implementation

## Summary

Yes, the current backend can support a dashboard, but only the first layer of metrics should rely on today's APIs alone.

The backend already exposes durable read surfaces for:

- assets
- jobs
- conversions
- outputs
- output actions

That is enough for a frontend to aggregate operational metrics today.

The current backend is not yet optimized for dashboard-scale aggregation because:

- `GET /assets` returns summary rows, not indexed metadata rollups
- `GET /jobs` returns the full list with no server-side filtering
- `GET /outputs` currently backfills and filters mostly in Python
- there is no dedicated dashboard summary endpoint
- the app still relies on `create_all()` instead of migrations, so schema changes should stay additive

## Current Capability Map

Metrics the backend already supports well enough for phase 1:

- asset counts
- storage totals from `file_size`
- indexing status counts
- recent registrations
- job status counts
- conversion status counts
- output counts, bytes, formats, and availability

Metrics that are technically available but inefficient to compute from current list contracts:

- total indexed duration
- total message count across indexed assets
- sensor-type mix
- modality coverage
- dataset row totals and manifest-derived dataset summaries across all outputs

Metrics that need richer extraction upstream in `hephaes`:

- missing modality combinations
- time-sync quality
- sparse or interrupted recording quality
- label coverage and scenario diversity

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

### Phase 1: Support Frontend Aggregation Without New Schema Work

Goal:

- let the frontend ship a dashboard using existing list routes

Dependencies:

- this phase can start immediately from the current API surface and does not require new `hephaes` work
- this phase is meant to run alongside frontend phase 1 so the first dashboard can ship against existing routes

Backend work in this phase should stay minimal:

- verify the existing list routes remain stable under concurrent dashboard reads
- keep response ordering deterministic
- document expected pagination and filter behavior
- add tests if the dashboard exposes previously untested combinations of statuses or empty states

No required schema changes in phase 1.

Optional small improvements:

- add server-side filters to `GET /jobs` if the frontend needs narrower polling
- expose a lightweight `limit` on routes that do not yet have one when practical

Exit criteria:

- the frontend can compute an operational dashboard using only current read APIs

### Phase 2: Add Dedicated Dashboard Summary APIs

Goal:

- make dashboard reads fast and stable for larger inventories

Dependencies:

- this phase depends on `hephaes` phase 1 so backend summary routes can reuse stable metric-derivation helpers instead of re-encoding heuristics ad hoc
- this phase unblocks frontend phase 2, which should switch from client aggregation to these backend-owned rollups

Recommended new routes:

- `GET /dashboard/summary`
- `GET /dashboard/trends`
- optionally `GET /dashboard/blockers`

Suggested `GET /dashboard/summary` payload areas:

- inventory summary
- indexing summary
- job summary
- conversion summary
- output summary
- freshness timestamps

Suggested fields:

- `asset_count`
- `total_asset_bytes`
- `registered_last_24h`
- `registered_last_7d`
- `indexing_status_counts`
- `job_status_counts`
- `failed_jobs_last_24h`
- `conversion_status_counts`
- `output_count`
- `total_output_bytes`
- `output_format_counts`
- `output_availability_counts`

Suggested `GET /dashboard/trends` payload areas:

- registrations by day
- job failures by day
- conversions by day
- outputs created by day

Implementation guidance:

- use SQL aggregation rather than materializing full lists in Python
- join `asset_metadata` only for metrics that truly need indexed fields
- keep time buckets backend-owned so chart semantics are consistent across clients

Recommended modules:

- `app/api/dashboard.py`
- `app/schemas/dashboard.py`
- `app/services/dashboard.py`

Exit criteria:

- dashboard routes return summary payloads without requiring the client to fetch whole tables
- aggregate computations remain correct for empty and mixed-status datasets

### Phase 3: Enrich Asset And Output Quality Rollups

Goal:

- support robotics-specific trust and readiness metrics, not just operational counts

Dependencies:

- this phase depends on `hephaes` phase 2 for opt-in bag-quality signals and `hephaes` phase 3 for manifest-level readiness signals
- this phase unblocks frontend phase 3 and should not begin until backend phase 2 contracts have settled

Recommended backend additions:

- derive dashboard-friendly quality summaries from `asset_metadata`
- surface rollups for `sensor_types_json`, `topics_json`, and manifest metadata
- expose blocker-style summaries such as missing metadata, failed indexing, or unavailable outputs

Prefer additive persistence if new durable state becomes necessary:

- additive tables are safer than altering constrained existing tables
- if caching is needed, prefer a new table such as `dashboard_snapshots` or `asset_quality_profiles`
- avoid changing `jobs.type` or similar constrained enums unless a migration layer is introduced first

Potential new summary fields:

- `total_indexed_duration_seconds`
- `total_indexed_message_count`
- `sensor_type_counts`
- `topic_modality_counts`
- `convertible_asset_count`
- `blocked_asset_count`
- `manifest_backed_output_count`
- `training_ready_output_count`

Exit criteria:

- the backend can answer dashboard questions about readiness and data quality without N+1 detail reads

### Phase 4: Optional Cached Snapshots For Large Local Catalogs

Goal:

- keep dashboard loads responsive if catalogs grow beyond comfortable live aggregation

Dependencies:

- keep this phase optional until backend phase 2 and phase 3 have real usage data showing live aggregation is no longer fast enough
- this phase should follow proven scale pressure, not precede it

Recommended approach:

- keep live summary computation as the source of truth first
- add snapshot caching only if real usage shows the need
- refresh snapshots on ingest, indexing completion, conversion completion, and output-action completion

This phase should remain optional until real scale demands it.

## Query And Performance Notes

The current output listing service is intentionally simple and does some filtering after materializing rows.
That is fine for the current local-first product stage, but the dashboard summary path should not reuse that pattern long-term.

When summary routes land:

- aggregate in SQL where possible
- minimize Python-side full-table scans
- keep output-artifact backfill bounded and explicit
- avoid dashboard requests that trigger surprising heavy filesystem inspection

## Testing Plan

- add API tests for summary and trend routes
- cover empty database cases explicitly
- cover mixed success and failure states across assets, jobs, conversions, and outputs
- verify timestamp bucket boundaries and UTC normalization
- add regression coverage for output rollups when artifacts are missing or invalid

## Suggested Backend Sequence

1. Ship frontend dashboard against current APIs.
2. Add dedicated dashboard schemas, service, and routes.
3. Move expensive or repetitive rollups into backend-owned aggregates.
4. Add richer quality and readiness summaries after `hephaes` exposes stable extraction helpers.
