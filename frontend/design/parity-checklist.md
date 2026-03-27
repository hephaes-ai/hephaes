# Frontend Desktop Parity Checklist

This checklist captures the minimum user-visible behavior that must continue to
work while `frontend/` is migrated from Next.js to a Tauri-hosted React app.

## Core Routes

- [ ] `/dashboard` loads summary cards and charts
- [ ] `/inventory` loads assets, filters, sorting, and selection state
- [ ] `/assets/:assetId` loads asset metadata, tags, jobs, and conversions
- [ ] `/jobs` loads history, filters, and refresh behavior
- [ ] `/jobs/:jobId` loads job details and linked entities
- [ ] `/outputs` loads outputs list, filters, presets, and selection state
- [ ] `/outputs/:outputId` loads output details and content links
- [ ] `/replay` loads visualization UI and selected asset episode state
- [ ] `/convert/new` loads authoring create mode
- [ ] `/convert/use` loads authoring use mode
- [ ] `/convert` still resolves to the correct create/use destination
- [ ] `/` still resolves to the default landing route
- [ ] `/visualize` still redirects to `/replay`

## Data And Connectivity

- [x] frontend can talk to a separately started FastAPI backend
- [x] backend health state is surfaced in the UI
- [ ] SWR polling and revalidation still work
- [x] REST requests still resolve against the configured backend base URL
- [x] replay WebSocket still connects successfully

## Inventory Flows

- [ ] search, type, status, tag, date, and size filters still work
- [x] tag creation and tag assignment still work
- [ ] bulk selection and bulk indexing controls still work
- [x] directory scan still works against the backend route
- [ ] upload flow still works or is intentionally replaced with equivalent behavior

## Conversion And Output Flows

- [ ] conversion authoring reads saved configs correctly
- [x] create conversion flow still works
- [ ] saved-config use flow still works
- [ ] outputs filtering and action triggers still work
- [ ] output content links still resolve correctly

## Replay Flows

- [ ] episode selection still works
- [ ] lane selection still works
- [ ] URL-driven replay state still works
- [ ] scrubber updates state correctly
- [ ] playback controls still work
- [ ] embedded Rerun viewer still loads backend-managed recordings

## Validation Commands

Run these during the migration:

```bash
cd frontend
npm run lint
npm test
npm run typecheck
npm run build
npm run desktop:build
cargo check --manifest-path /Users/danielyoo/workspace/hephaes/frontend/src-tauri/Cargo.toml
npm run tauri:dev
```

## Validation Snapshot

Validated on `2026-03-27` with both the standalone backend and the bundled
desktop sidecar.

Verified:

- automated frontend checks passed:
  - `npm run lint`
  - `npm test`
  - `npm run typecheck`
  - `npm run build`
  - `npm run desktop:build`
  - `cargo check --manifest-path /Users/danielyoo/workspace/hephaes/frontend/src-tauri/Cargo.toml`
  - `npm run tauri:dev`
- live backend endpoints returned real data for:
  - `/health`
  - `/assets`
  - `/assets/:assetId`
  - `/assets/:assetId/episodes`
  - `/jobs`
  - `/outputs`
  - `/conversion-configs`
  - `/conversions`
- Vite desktop dev server served SPA entry responses for:
  - `/dashboard`
  - `/replay?asset_id=...`
- packaged `Hephaes.app` launched its bundled sidecar automatically on dynamic
  loopback ports
- forced sidecar termination surfaced an actionable desktop error path and left
  no orphan backend process behind
- packaged app logs were written to:
  - `~/Library/Logs/ai.hephaes.desktop/desktop.log`
  - `~/Library/Logs/ai.hephaes.desktop/backend/backend.log`
  - `~/Library/Logs/ai.hephaes.desktop/backend/backend-access.log`
- packaged sidecar API smoke passed for:
  - `/health`
  - `/dashboard/summary`
  - `/assets`
  - `/jobs`
  - `/outputs`
  - `/conversion-configs`
  - `/conversions`
- packaged sidecar mutation smoke passed against
  `/Users/danielyoo/workspace/hephaes/hephaes/demo/input/ros2.mcap` for:
  - `POST /assets/scan-directory`
  - `POST /tags`
  - `POST /assets/:assetId/tags`
  - `POST /assets/:assetId/index`
  - replay websocket handshake at `/assets/:assetId/episodes/:episodeId/replay`
  - `POST /conversions`
  - `GET /outputs/:outputId`
- packaged build parity uncovered and fixed a PyInstaller packaging gap for
  `rosbags.typesys.stores.empty`, which had been breaking release-mode indexing

Still requires an interactive manual pass:

- route-by-route UI confirmation inside the running desktop shell
- filter-heavy UI behaviors such as inventory and outputs filtering
- embedded Rerun viewer confirmation inside the packaged webview
