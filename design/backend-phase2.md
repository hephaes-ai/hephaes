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
