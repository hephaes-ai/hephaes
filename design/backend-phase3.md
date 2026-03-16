# Backend Phase 3

## Goal

Add search and filtering so the frontend can browse the local asset library through backend queries instead of loading everything client-side.

This phase assumes phase 2 metadata persistence is already in place.

## Scope

Extend `GET /assets` to support query parameters such as:

- `search`
- `type`
- `status`
- `min_duration`
- `max_duration`
- `start_after`
- `start_before`

Examples:

- `GET /assets`
- `GET /assets?search=test_run`
- `GET /assets?type=mcap&status=indexed`
- `GET /assets?min_duration=60`

## Query Strategy

Use SQLite queries only in this phase. Do not add Elasticsearch or OpenSearch for a local-first MVP.

Suggested filtering sources:

- `assets.file_name`
- `assets.file_type`
- `assets.indexing_status`
- `asset_metadata.duration`
- `asset_metadata.start_time`
- `asset_metadata.end_time`

Search can begin as a case-insensitive filename match.

## API Behavior

`GET /assets` should return:

- asset base fields
- optionally selected metadata fields needed for list views
- pagination metadata if the list grows beyond a comfortable local size

Suggested query handling rules:

- combine filters when multiple params are present
- ignore unsupported empty params
- return stable ordering, such as newest registered first

## Deliverable

By the end of phase 3, you should be able to:

- search assets by filename
- filter by type
- filter by indexing status
- filter by duration and time ranges
- power the frontend list and search results from SQLite only

## Tasks

### Query contract

- Decide on the exact `GET /assets` query parameter contract for phase 3.
- Add support for:
  - `search`
  - `type`
  - `status`
  - `min_duration`
  - `max_duration`
  - `start_after`
  - `start_before`
- Define how empty or missing query params are handled so the route stays forgiving for frontend usage.
- Decide whether pagination ships in phase 3 or remains a later extension, and document the response shape clearly either way.

### Query implementation

- Extend the asset listing query to apply search and filters in SQLite instead of client-side only.
- Add the join path needed so `assets` can be filtered against `asset_metadata` fields without requiring a separate lookup pass.
- Implement case-insensitive filename search against `assets.file_name`.
- Implement filtering for:
  - `assets.file_type`
  - `assets.indexing_status`
  - `asset_metadata.duration`
  - `asset_metadata.start_time`
  - `asset_metadata.end_time`
- Make filter combinations composable so multiple query params can be applied in one request.
- Preserve stable ordering, such as newest registered first, unless an explicit sort contract is introduced.

### Service boundaries

- Decide whether filtered listing stays in [backend/app/services/assets.py](/Users/danielyoo/workspace/hephaes/backend/app/services/assets.py) or moves into a dedicated search or listing service.
- Keep route handlers thin and push filtering logic into a reusable service-layer function.
- Keep the implementation structured so later phases can add pagination, tags, and richer metadata-backed search without rewriting the query layer.

### Schema and response shape

- Update [backend/app/schemas/assets.py](/Users/danielyoo/workspace/hephaes/backend/app/schemas/assets.py) for any new list-response envelope or pagination metadata if phase 3 returns more than a bare list.
- Decide whether `GET /assets` should continue returning only base asset fields or include selected metadata fields useful for list views.
- Keep list item schemas stable enough that the frontend can adopt backend-driven search and filters without another response-shape churn immediately after.

### Route updates

- Update [backend/app/api/assets.py](/Users/danielyoo/workspace/hephaes/backend/app/api/assets.py) so `GET /assets` accepts and validates the new query parameters.
- Ignore unsupported empty params rather than treating them as hard errors where reasonable.
- Return clear validation errors for malformed numeric or datetime query values.

### Filtering semantics

- Decide how unindexed assets behave when metadata-based filters such as duration or time range are supplied.
- Make duration filtering behavior explicit when an asset has no `asset_metadata` row yet.
- Decide whether time range filters apply to `start_time`, `end_time`, or both, and keep that behavior documented and testable.
- Ensure combined filters do not accidentally exclude valid rows because of inner joins or null metadata fields.

### Tests

- Add backend tests for filename search.
- Add tests for filtering by file type and indexing status.
- Add tests for duration and time-range filters against indexed assets.
- Add tests for combined query params.
- Add tests confirming empty query params are ignored when intended.
- Add tests for unindexed assets and null metadata behavior.
- Add tests for stable ordering of filtered and unfiltered results.

### Local verification

- Run the backend locally and register multiple assets with a mix of types and indexing statuses.
- Confirm `GET /assets` can narrow results by filename search.
- Confirm duration and time-range filters behave correctly after assets are indexed.
- Confirm the frontend can adopt the new query params without needing client-only filtering for the same cases.
