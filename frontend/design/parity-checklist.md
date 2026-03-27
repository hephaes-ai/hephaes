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

- [ ] frontend can talk to a separately started FastAPI backend
- [ ] backend health state is surfaced in the UI
- [ ] SWR polling and revalidation still work
- [ ] REST requests still resolve against the configured backend base URL
- [ ] replay WebSocket still connects successfully

## Inventory Flows

- [ ] search, type, status, tag, date, and size filters still work
- [ ] tag creation and tag assignment still work
- [ ] bulk selection and bulk indexing controls still work
- [ ] directory scan still works against the backend route
- [ ] upload flow still works or is intentionally replaced with equivalent behavior

## Conversion And Output Flows

- [ ] conversion authoring reads saved configs correctly
- [ ] create conversion flow still works
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
```
