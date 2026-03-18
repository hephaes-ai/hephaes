# Jobs And Conversions

## Jobs Overview

The jobs experience is split across two route components:

- `components/jobs-page.tsx`
- `components/job-detail-page.tsx`

Together they expose the backend's durable workflow history without turning the frontend into a full job-orchestration dashboard.

Supported job types today:

- `index`
- `convert`
- `prepare_visualization`

## Jobs List

`JobsPage` is a searchable monitor for durable backend work.

### Data sources

The page loads:

- all jobs through `useJobs()`
- all assets through `useAssets()`

Asset data is only used to render friendly target labels for job-linked asset IDs.

### Filters

The jobs page stores its filters in the URL:

- `type`
- `status`

Filtering stays client-side after the full jobs list is fetched, which keeps the route simple and preserves fast filter changes.

### Polling

If any job is `queued` or `running`, the page polls every 1.5 seconds. Otherwise it stays idle.

### Table design

Each row shows:

- job type
- workflow status
- target assets as compact links
- created time
- updated time
- open action

This page is designed as a monitor and navigation surface, not a place to mutate jobs.

## Job Detail

`JobDetailPage` expands a single durable job and connects it back to asset and conversion context.

### Data sources

The page loads:

- the job itself through `useJob(jobId)`
- asset summaries through `useAssets()`
- conversion summaries through `useConversions()`
- conversion detail through `useConversion()` when a matching conversion summary exists for the job

That lets the page enrich the job record with output-file details when the job belongs to a conversion workflow.

### Polling behavior

The page polls while either of these are active:

- the job status
- the matched conversion status

During that loop it refreshes:

- the job detail
- the jobs list
- the conversions list
- the conversion detail when applicable

### Sections

The job detail page is organized into:

- top summary card with refresh action
- failure alert when `error_message` is present
- job details card
- target assets card
- config JSON card when `config_json` is non-empty
- conversion output card when the job maps to a conversion

### Conversion output handling

If the job is linked to a conversion, the page shows:

- conversion status
- created time
- output path
- output files
- conversion error state

This avoids making users jump to a separate conversion-detail route that does not currently exist.

## Conversion Dialog

`components/conversion-dialog.tsx` is the main mutation surface for backend conversions.

It is opened from:

- the inventory page for selected assets
- the asset detail page for the current asset

## Conversion Form Model

The dialog keeps a structured local form state with four areas:

- output format
- mapping mode
- resampling options
- manifest generation

### Output formats

Supported formats:

- Parquet
- TFRecord

Each format only reveals its relevant compression options.

### Mapping modes

The dialog supports:

- automatic mapping
- custom JSON mapping

Custom mapping is validated before submission. The validator ensures the JSON is an object whose keys are non-empty output fields and whose values are non-empty topic lists.

### Resampling

Optional resampling can be enabled with:

- frequency in Hz
- method: `downsample` or `interpolate`

The dialog blocks submission if the frequency is not a positive number.

### Manifest output

The user can ask the backend to write a manifest alongside the conversion output.

## Conversion Guardrails

The dialog intentionally blocks submission when:

- no assets are selected
- a submission is already in progress
- any selected asset is not indexed
- the custom mapping is invalid
- the resampling frequency is invalid

That keeps conversion requests aligned with the backend's expected prerequisites.

## Submission And Follow-Up

On submit, the dialog:

1. builds a `ConversionCreateRequest`
2. creates the conversion through `createConversion()`
3. stores the returned `ConversionDetail`
4. revalidates related asset, job, and conversion data

Once created, the dialog flips from input mode into status mode instead of closing immediately.

The post-submit state shows:

- conversion ID
- conversion status
- linked job status
- created time
- output path
- selected asset count
- output files when available
- a direct link to the linked job detail page

## Conversion Polling

If the created conversion or its job is still active, the dialog polls `getConversion()` every 1.5 seconds while it remains open. Poll results also trigger revalidation of:

- related asset detail pages
- conversion detail cache
- conversion list
- jobs list

This keeps the conversion dialog useful as a live handoff surface rather than a fire-and-forget submit button.

## Shared Workflow Semantics

Jobs, conversions, and replay preparation all share a consistent status vocabulary:

- `queued`
- `running`
- `succeeded`
- `failed`

`components/workflow-status-badge.tsx` and `lib/format.ts` intentionally keep that language and styling aligned across the app.
