# Assets, Indexing, And Tags

## Asset Domain

Assets are the main user-facing entities in the backend. Everything else builds on top of them:

- tags attach to assets
- indexing enriches assets
- conversions target assets
- jobs often target assets
- replay and visualization flows start from assets

## Asset Ingestion Flows

The backend currently supports four ingestion paths.

### File-path registration

`POST /assets/register`

Behavior:

- normalize the path to an absolute local path
- ensure the path exists and is a file
- inspect `file_name`, `file_type`, and `file_size`
- reject duplicate `file_path` values
- create an asset with `indexing_status="pending"`

This is the simplest and most direct ingestion path.

### Binary upload

`POST /assets/upload`

Behavior:

- require `X-File-Name`
- validate the file name and supported extension
- reject empty payloads
- write bytes into `data/raw/`
- register the written file as a managed asset
- remove the file again if registration fails

Uploads currently support `.bag` and `.mcap`.

### Native file picker registration

`POST /assets/register-dialog`

Behavior:

- try macOS `osascript` first when available
- fall back to a Tk-based file picker
- allow cancel without failure
- register selected files one by one
- report duplicates and invalid paths as structured skips

This route is intentionally desktop-oriented and can return `503` when the local environment cannot open a picker.

### Directory scan

`POST /assets/scan-directory`

Behavior:

- validate the directory path
- recursively or non-recursively enumerate supported files
- register discovered assets one by one
- return discovered count, newly registered assets, and skipped duplicates/invalid files

This keeps bulk ingestion backend-owned instead of requiring the frontend to walk directories itself.

## Asset Listing And Detail

### List endpoint

`GET /assets`

The asset list supports these filters:

- `search`
- `tag`
- `type`
- `status`
- `min_duration`
- `max_duration`
- `start_after`
- `start_before`

Implementation details:

- filename search is case-insensitive
- tag and file type are normalized to lowercase
- duration and start-time filters trigger an outer join against `asset_metadata`
- tag filters trigger a join through the tag relationship
- results are ordered newest-first by `registered_time`, then `id`

The response includes summary tags so the frontend can render inventory rows without making extra tag calls.

### Detail endpoint

`GET /assets/{asset_id}`

Asset detail is assembled dynamically and includes:

- the asset row
- indexed metadata if present
- tags
- derived episode summaries
- related jobs
- related conversions

That makes asset detail the backend's composition-heavy read surface.

## Episode Summaries From Assets

`GET /assets/{asset_id}/episodes`

Episode summaries are not read from a separate table. They are derived from the indexed metadata record:

- default episode payload
- start and end timestamps
- visualization summary

If the asset has not been indexed yet, the backend raises `EpisodeDiscoveryUnavailableError` and the route returns `422`.

## Indexing Workflow

### Entry points

The backend currently exposes two indexing entry points:

- `POST /assets/{asset_id}/index`
- `POST /assets/reindex-all`

### Service design

`app/services/indexing.py` owns indexing.

The flow for a single asset is:

1. resolve the asset
2. create a durable `index` job
3. mark the asset as `indexing`
4. mark the job as `running`
5. profile the file through `hephaes.Profiler`
6. build the indexed metadata payload
7. upsert `asset_metadata`
8. mark the asset `indexed` and update `last_indexed_time`
9. mark the job `succeeded`

On failure:

- the transaction is rolled back
- the asset metadata record is upserted with `indexing_error`
- the asset is marked `failed`
- the job is marked `failed`

### Metadata derived during indexing

The indexing service stores:

- duration
- start and end times
- topic count
- message count
- normalized topic summaries
- inferred sensor types
- raw profiler metadata
- a default episode summary
- a visualization summary

### Topic modality inference

The current modality and sensor-type model is heuristic and message-type driven. For example:

- image-like message types become `image`
- point cloud, laser, and scan types become `points`
- IMU and telemetry-style types become `scalar_series`
- everything else becomes `other`

That heuristic is what powers:

- frontend modality labels
- visualization readiness
- replay lane counts

## Reindex-All Behavior

`reindex_all_pending_assets()` targets assets that are:

- `pending`
- `failed`
- or missing `last_indexed_time`

The service indexes those assets in registration order and returns:

- successfully indexed assets
- failed assets

It creates one job per asset rather than a single batch job.

## Tag Model

Tags are intentionally lightweight and case-insensitive.

### Create tag

`POST /tags`

Behavior:

- trim the provided name
- store a display name plus lowercase `normalized_name`
- reject case-insensitive duplicates

### List tags

`GET /tags`

Tags are returned:

- sorted by normalized name
- with `asset_count`

### Attach tag to asset

`POST /assets/{asset_id}/tags`

Behavior:

- validate the asset and tag
- reject duplicate attachments with `409`
- return the refreshed asset detail payload

### Remove tag from asset

`DELETE /assets/{asset_id}/tags/{tag_id}`

Behavior:

- validate the asset and tag
- remove the join row
- delete the tag itself if it is no longer attached to any asset

That last behavior keeps the tag catalog focused on tags that are still in use.

## Related-Workflow Lookup

Asset detail also exposes recent jobs and conversions related to an asset.

Current implementation detail:

- the service queries jobs or conversions ordered newest-first
- then filters them in Python by whether the asset ID appears in the target/source asset ID JSON list

This is simple and sufficient now, though it is not the most SQL-efficient design for a much larger dataset.

## Design Intent So Far

The asset layer is designed to do three things well:

- make it easy to get files into the app
- turn raw files into richer indexed metadata incrementally
- provide a single asset-centered read model that supports the rest of the product
