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
