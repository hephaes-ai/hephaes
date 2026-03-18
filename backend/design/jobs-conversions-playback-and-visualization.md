# Jobs, Conversions, Playback, And Visualization

## Durable Jobs

The backend uses the `jobs` table plus `app/services/jobs.py` to track workflow state for long-running or workflow-like operations.

Supported job types today:

- `index`
- `convert`
- `prepare_visualization`

Supported statuses:

- `queued`
- `running`
- `succeeded`
- `failed`

## Job Service

`JobService` provides a small state machine:

- `create_job()`
- `mark_job_running()`
- `mark_job_succeeded()`
- `mark_job_failed()`

It also provides lookup helpers:

- `list_jobs()`
- `get_job_or_raise()`
- `find_latest_job_for_target()`

`find_latest_job_for_target()` is especially important for visualization prep because it lets the backend reuse an in-flight or cached job for the same asset plus episode.

## Jobs API

The public jobs surface is intentionally minimal:

- `GET /jobs`
- `GET /jobs/{job_id}`

The jobs API is read-only for now. Jobs are created as side effects of other workflow APIs.

## Conversion Workflow

### Entry point

`POST /conversions`

### Service design

`app/services/conversions.py` owns conversion execution.

The flow is:

1. resolve and validate all target assets
2. require indexed metadata so topics are available
3. resolve the mapping
4. build conversion config
5. create a durable `convert` job
6. create a `conversions` row
7. mark both job and conversion as running
8. execute `hephaes.Converter`
9. persist output files and success state, or persist failure state

### Mapping behavior

The backend supports:

- automatic mapping from the first asset's indexed topics
- custom mapping from the request payload

Custom mappings are built through `build_mapping_template_from_json()` with:

- strict unknown-topic checking
- no requirement that every topic be consumed

### Output formats

The conversion API currently supports:

- Parquet
- TFRecord

Optional resampling is supported with:

- frequency in Hz
- method `interpolate` or `downsample`

### Output location

Every conversion writes to:

- `outputs/conversions/<conversion_id>/`

The job and conversion record both point at that output directory.

## Episode Playback Model

The playback APIs are implemented in `app/services/episodes.py` and exposed from `app/api/episodes.py`.

### Current episode model

Episodes are currently derived rather than persisted. For an indexed asset, the backend exposes one default episode based on the indexed metadata record.

### Episode detail

`GET /assets/{asset_id}/episodes/{episode_id}`

The backend builds episode detail by combining:

- derived episode summary
- topic-based stream seeds from `asset_metadata.topics_json`
- first and last stream timestamps read from the raw asset through `RosReader`

Each stream includes:

- stable stream ID
- stream key
- source topic
- message type
- modality
- message count
- rate
- first and last timestamp
- small metadata JSON

## Timeline API

`GET /assets/{asset_id}/episodes/{episode_id}/timeline`

The timeline route returns scrubber lane data rather than raw messages.

Implementation shape:

- select the requested streams, or all streams if none are specified
- compute bucket counts across the episode duration
- reread message headers from the raw asset
- count events per stream per bucket
- return lane summaries plus bucketed counts

This is optimized for timeline rendering, not full payload inspection.

## Samples API

`GET /assets/{asset_id}/episodes/{episode_id}/samples`

The samples API supports two selection modes:

- nearest sample for non-scalar visual streams
- windowed samples for scalar-series streams when a non-zero window is requested

Implementation shape:

- read raw messages through `RosReader`
- normalize payloads through `hephaes._converter_helpers._normalize_payload`
- attach lightweight modality-specific metadata summaries
- return stream-grouped sample collections

This gives the frontend a synchronized inspection surface without shipping the whole recording.

## Visualization Preparation

### Entry points

- `POST /assets/{asset_id}/episodes/{episode_id}/prepare-visualization`
- `GET /assets/{asset_id}/episodes/{episode_id}/viewer-source`

### Service design

`app/services/visualization.py` owns the Rerun artifact lifecycle.

The flow for preparation is:

1. validate the asset and episode
2. resolve current viewer and recording version expectations from settings
3. look for the latest matching `prepare_visualization` job
4. validate any cached artifact and sidecar metadata
5. reuse a running or cached-success job when possible
6. otherwise create and run a new `prepare_visualization` job
7. generate `recording.rrd`
8. write `recording.meta.json`
9. mark the job succeeded or failed

### Artifact generation

`_generate_rrd()` currently:

- imports `rerun`
- opens the asset through `RosReader`
- iterates messages for the selected topics
- normalizes payloads
- logs supported payloads to Rerun
- writes the resulting binary stream to disk as `recording.rrd`

Current logging behavior is intentionally narrow:

- image-like payloads become `rr.Image` when byte content can be decoded
- point payloads become `rr.Points3D` when structured point lists are available
- everything else falls back to `rr.TextLog`

### Viewer-source manifest states

`get_viewer_source()` returns one of four states:

- `none`
- `preparing`
- `ready`
- `failed`

The ready manifest includes:

- `source_kind`
- `source_url`
- `job_id`
- `artifact_path`
- `viewer_version`
- `recording_version`
- `updated_at`

### Cache validation

Prepared artifacts are only considered valid when both the `.rrd` file and `.meta.json` sidecar exist and match:

- asset ID
- episode ID
- viewer version
- recording version

If either artifact or metadata is stale or incomplete, the backend invalidates the cache and reports that regeneration is needed.

### Static serving

The prepared `.rrd` file is served through the app's static mount under `/visualizations`, so the frontend consumes a backend-owned URL instead of a filesystem path.

## Design Intent So Far

These workflow modules are aimed at a middle ground:

- durable enough for the frontend to monitor and revisit work
- simple enough to run in one local API process
- rich enough to support replay and output-generation features without introducing a full distributed job system yet
