# Backend Phase 2

## Goal

Add indexing and metadata persistence so the app can do more than register files. After this phase, the backend should be able to inspect a registered asset, extract metadata, and persist it for frontend detail views and filtering.

## Scope

Introduce an `asset_metadata` table keyed by `asset_id`.

Suggested fields:

- `asset_id`
- `duration`
- `start_time`
- `end_time`
- `topic_count`
- `message_count`
- `sensor_types_json`
- `topics_json`
- `default_episode_json`
- `visualization_summary_json`
- `raw_metadata_json`
- `created_at`
- `updated_at`

The flexible fields should be stored as JSON so the schema can evolve without immediate table churn.

## Indexing Flows

Implement these backend actions:

- `POST /assets/{asset_id}/index`
- `POST /assets/reindex-all`

When indexing runs, the backend should:

- load the file from local disk
- call into `hephaes` for metadata extraction when possible
- persist extracted metadata in `asset_metadata`
- persist topic summaries and modality hints needed for later visualization
- record a default episode summary for raw one-file recordings so the frontend can treat an indexed asset as visualizable without extra inference
- update `assets.indexing_status`
- update `assets.last_indexed_time`
- record failure details if indexing fails

In this phase, indexing can still run synchronously inside the backend process. Durable job tracking comes later.

## API Surface

Add these routes:

- `POST /assets/{asset_id}/index`
- `POST /assets/reindex-all`

Update this route:

- `GET /assets/{asset_id}` should return the base asset plus metadata

Suggested detail response shape:

```json
{
  "asset": {
    "id": "uuid",
    "file_path": "/absolute/path/to/file.mcap",
    "file_name": "file.mcap",
    "file_type": "mcap",
    "file_size": 123456,
    "registered_time": "2026-03-14T10:00:00Z",
    "indexing_status": "indexed",
    "last_indexed_time": "2026-03-14T10:05:00Z"
  },
  "metadata": {
    "duration": 93.2,
    "start_time": "2026-03-14T09:58:00Z",
    "end_time": "2026-03-14T09:59:33Z",
    "topic_count": 12,
    "message_count": 10455,
    "sensor_types": ["camera", "imu"],
    "topics": [
      {
        "name": "/camera/front/image_raw",
        "message_type": "sensor_msgs/Image",
        "message_count": 930,
        "rate_hz": 10.0,
        "modality": "image"
      }
    ],
    "default_episode": {
      "episode_id": "asset-uuid:default",
      "label": "Episode 1",
      "duration": 93.2
    },
    "visualization_summary": {
      "has_visualizable_streams": true,
      "default_lane_count": 3
    },
    "raw_metadata": {}
  }
}
```

## Service Boundaries

Create a dedicated indexing service so route handlers stay thin.

Suggested internal shape:

- `services/indexing.py`
- `IndexingService.index_asset(asset_id)`
- `IndexingService.reindex_all_pending_assets()`

This service should be designed so it can later run in-process, in a background task, or in a worker without changing the API contract.

It should also produce normalized topic and episode summaries that later phases can expose through visualization and playback APIs without re-indexing the asset.

## Deliverable

By the end of phase 2, you should be able to:

- trigger indexing for one asset
- reindex all pending or stale assets
- store metadata in SQLite
- return a useful asset detail response for the frontend detail page
- tell the frontend whether an indexed asset has streams that can be visualized later

## Tasks

### Database schema

- Add an `asset_metadata` model in [backend/app/db/models.py](/Users/danielyoo/workspace/hephaes/backend/app/db/models.py) keyed by `asset_id`.
- Include fields for duration, start and end time, topic count, message count, sensor types, topics, default episode summary, visualization summary, raw metadata, and timestamps.
- Use JSON-capable columns where practical for flexible structures such as topic lists and raw metadata.
- Add the relationship or lookup path needed so an asset and its metadata can be loaded together cleanly.
- Ensure database initialization creates the new table automatically alongside `assets`.

### Metadata extraction

- Decide on the phase 2 extraction entrypoint from `hephaes`, likely using the profiling utilities in `src/hephaes/`.
- Extract temporal metadata such as duration, start time, end time, and message count from the selected asset file.
- Extract topic summaries including topic name, message type, message count, and rate.
- Derive simple modality hints such as image or non-image where possible so later visualization phases have a usable summary.
- Build a default episode summary for a single raw file so later frontend flows can treat the asset as one visualizable episode by default.
- Preserve a raw metadata payload for future debugging and schema evolution.

### Indexing service

- Create [backend/app/services/indexing.py](/Users/danielyoo/workspace/hephaes/backend/app/services/indexing.py).
- Implement `IndexingService.index_asset(asset_id)` for one-asset indexing.
- Implement `IndexingService.reindex_all_pending_assets()` for bulk indexing of pending or stale assets.
- Resolve the asset record to its local file path before calling into `hephaes`.
- Set `assets.indexing_status` to `indexing` before work starts.
- Persist metadata and update `last_indexed_time` when indexing succeeds.
- Set `assets.indexing_status` to `failed` when indexing fails and capture enough failure detail to debug the run.
- Keep the service API clean enough that later job-based execution can wrap it without changing route contracts.

### API schemas

- Update [backend/app/schemas/assets.py](/Users/danielyoo/workspace/hephaes/backend/app/schemas/assets.py) with response models for asset metadata and indexed topic summaries.
- Extend the asset detail response so it returns both the base asset and metadata.
- Add response models for single-asset indexing and bulk reindexing if the routes return anything beyond the updated asset detail.
- Keep schema names specific enough that tag, job, and visualization fields can be added later without a rename churn.

### API routes

- Update [backend/app/api/assets.py](/Users/danielyoo/workspace/hephaes/backend/app/api/assets.py) to add `POST /assets/{asset_id}/index`.
- Update [backend/app/api/assets.py](/Users/danielyoo/workspace/hephaes/backend/app/api/assets.py) to add `POST /assets/reindex-all`.
- Route both indexing endpoints through the dedicated indexing service instead of embedding the logic in the route handlers.
- Update `GET /assets/{asset_id}` so it loads and returns persisted metadata when available.
- Return clear failure responses for missing assets, invalid files, and indexing errors.

### State handling

- Decide how failed indexing details should be stored in phase 2, either on the metadata row or on the asset row if that is simpler for the MVP.
- Avoid leaving an asset stuck in `indexing` when an exception interrupts the flow.
- Make reindex behavior explicit for already indexed assets so the route contract stays predictable.

### Tests

- Add backend tests covering successful indexing of a registered asset.
- Add tests for `GET /assets/{asset_id}` returning metadata after indexing.
- Add tests for reindexing multiple pending assets.
- Add tests for indexing failure behavior, including status transitions and error handling.
- Mock or isolate `hephaes` profiling work where needed so the backend tests stay fast and deterministic.

### Local verification

- Run the backend locally and index a real `.bag` or `.mcap` asset through the new route.
- Confirm that the `asset_metadata` row is persisted in SQLite.
- Confirm that `GET /assets/{asset_id}` returns the new metadata payload shape.
- Confirm that the asset status changes from `pending` to `indexing` to `indexed`, or to `failed` when extraction breaks.
