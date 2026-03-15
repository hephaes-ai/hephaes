# Backend Phase 7

## Goal

Improve local file ingestion so the app has a smoother workflow for bringing files into the system.

## Ingestion Options

### Option A: Register file or folder paths

The frontend sends:

- a file path
- or a directory path for scanning

The backend scans for supported file types such as `.bag` and `.mcap`.

Pros:

- fast for local power users
- simple backend logic

Cons:

- browser apps do not always handle arbitrary local paths cleanly
- more environment-dependent UX

### Option B: Upload files through the frontend

The frontend uploads files to the backend, and the backend stores them in a managed directory such as:

- `backend/data/raw/`

Pros:

- more consistent web-app behavior
- easier to reason about ownership and file lifecycle

Cons:

- requires file copy and storage management
- larger files may take time to upload even locally

## Recommendation

Phase 1 starts with path registration because it is the fastest way to get the app working. Once the rest of the backend is in place, upload is usually the more stable long-term default because it gives the backend a predictable managed location. Path registration and folder scanning can remain available for advanced local workflows.

## API Surface

Potential routes:

- `POST /assets/upload`
- `POST /assets/register`
- `POST /assets/scan-directory`

## Asset Detail Expansion

At this point, `GET /assets/{asset_id}` should be an aggregated endpoint that can return:

- base asset info
- extracted metadata
- tags
- related jobs
- prior conversions

That allows the frontend detail page to load from one main request instead of stitching together several calls.

## Deliverable

By the end of phase 7, you should have:

- a stable local ingestion story
- a managed path for uploaded files
- optional directory scanning for advanced users
- a richer asset detail endpoint for the frontend
