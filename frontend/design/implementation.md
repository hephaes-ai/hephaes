# Frontend Runtime Implementation Plan

## Goal

Collapse `frontend/` to a single Vite-powered React app that works cleanly with
Tauri, while removing legacy web assumptions from desktop startup and asset
ingestion.

## Guiding Constraints

- keep the app usable while migration is in progress
- keep the current backend API contract intact
- do not leave Next and Vite as permanent parallel runtimes
- ship in phases with validation after each phase
- keep `frontend/design/current-state.md` updated as implementation proceeds

## Scope

In scope:

- unifying frontend runtime ownership under Vite
- unifying routing under React Router
- making the runtime boundary explicit
- fixing desktop startup behavior
- fixing desktop asset-ingestion behavior
- retiring Next-specific app composition

Out of scope:

- redesigning backend APIs
- rewriting major product workflows
- a full component-library redesign

## Phase Summary

| Phase | Goal |
| --- | --- |
| 1 | Define and stabilize the runtime boundary |
| 2 | Make desktop startup non-blocking and explicit |
| 3 | Separate route ownership from the Next app tree |
| 4 | Migrate screens into Vite-owned route modules |
| 5 | Remove legacy web assumptions from asset ingestion |
| 6 | Retire the Next app surface and clean up build/runtime drift |
| 7 | Validate, document, and close the migration |

Current status:

- Phase 1 completed on `2026-03-28`
- Phase 2 completed on `2026-03-28`
- Phase 3 completed on `2026-03-28`
- Phase 4 completed on `2026-03-28`
- Phase 5 completed on `2026-03-28`
- Phase 6 completed on `2026-03-28`
- Phase 7 pending

## Phase 1: Runtime Boundary Contract

### Goal

Create one explicit runtime abstraction that the Vite app can use regardless
of platform mode.

### Status

Completed on `2026-03-28`.

### Tasks

- Define a normalized runtime snapshot shape with:
  - mode
  - status
  - base URL
  - log locations
  - capabilities
- Add explicit capability fields for:
  - native file dialog
  - native directory dialog
  - path asset registration
  - browser upload
- Update the Rust-side snapshot shape to support the new contract.
- Update TypeScript runtime helpers and hooks to normalize and expose this
  contract.
- Add or update tests around runtime loading and subscription behavior.
- Record the baseline in `frontend/design/current-state.md`.

### Implemented In This Phase

- Added a normalized `FrontendRuntimeSnapshot` TypeScript contract with:
  - `mode`
  - `status`
  - `baseUrl`
  - `error`
  - `backendLogDir`
  - `desktopLogDir`
  - `capabilities`
- Added `FrontendCapabilities` to the Tauri runtime snapshot and aligned mode
  names with the Vite-side contract.
- Normalized runtime loading so browser mode also resolves through the same
  runtime loader.
- Updated runtime consumers to read through the shared frontend runtime hook.
- Added runtime normalization and subscription tests in the frontend unit
  suite.

### Likely Files

- `frontend/src-tauri/src/lib.rs`
- `frontend/src/lib/backend-runtime.ts`
- `frontend/src/hooks/use-desktop-backend-runtime.ts`
- `frontend/src/bootstrap-app.tsx`
- `frontend/design/current-state.md`

### Exit Criteria

- runtime state is explicit and serializable
- feature code has one source of truth for platform capabilities
- desktop and web runtime assumptions are no longer implicit

## Phase 2: Non-Blocking Desktop Startup

### Goal

Make startup behavior match the intended desktop UX.

### Status

Completed on `2026-03-28`.

### Tasks

- Move sidecar startup off the blocking Tauri setup path.
- Emit `loading` runtime status before backend readiness.
- Ensure the Vite app renders immediately and shows startup UI.
- Drive failure and stopped states from runtime updates.
- Add tests for:
  - loading screen
  - startup failure state
  - stopped-runtime state
- Verify backend-status and runtime-monitor behavior against the new status
  model.

### Implemented In This Phase

- Moved backend runtime initialization off the blocking Tauri `.setup()` path
  and into a background thread.
- Kept the frontend startup screen mounted while the runtime snapshot remains
  `loading`.
- Made bootstrap state respond to live runtime updates so `loading -> ready`
  and `loading -> failed/stopped` are observable in React.
- Added bootstrap tests for:
  - loading to ready
  - loading to stopped before startup completes
- Revalidated the desktop bundle after the startup lifecycle change.

### Likely Files

- `frontend/src-tauri/src/lib.rs`
- `frontend/src/bootstrap-app.tsx`
- `frontend/src/components/backend-runtime-monitor.tsx`
- `frontend/src/components/backend-connection-notice.tsx`
- `frontend/src/bootstrap-app.test.tsx`

### Validation

- `cargo check --manifest-path frontend/src-tauri/Cargo.toml`
- `npm test`
- manual `npm run tauri:dev`

### Exit Criteria

- the desktop webview renders while the backend is still starting
- startup failure no longer appears as a blank or stalled app
- runtime lifecycle is observable from the frontend

## Phase 3: Route Ownership Separation

### Goal

Stop treating the Next app tree as the active source of route composition.

### Status

Completed on `2026-03-28`.

### Tasks

- Define a Vite-owned route tree under `frontend/src`.
- Introduce route modules or route wrappers in `frontend/src/routes`.
- Remove direct dependence on `frontend/app/*/page.tsx` from `frontend/src/App.tsx`.
- Keep feature screens reusable, but make the Vite app own route composition.
- Reduce dependence on alias-based router swapping for core app structure.
- Update `current-state.md` with the new route ownership status.

### Implemented In This Phase

- Moved the desktop route tree into a Vite-owned module at
  `frontend/src/routes/desktop-routes.tsx`.
- Removed direct imports of `frontend/app/*/page.tsx` from `frontend/src/App.tsx`.
- Rebuilt the route wrappers in Vite-owned code while keeping the underlying
  screen modules in place under `frontend/app`.
- Revalidated both the Next build and the Vite desktop build to keep the
  migration state stable across both active runtimes.

### Likely Files

- `frontend/src/App.tsx`
- `frontend/src/routes/*`
- `frontend/src/lib/app-routing.react-router.tsx`
- `frontend/vite.config.ts`
- selected files in `frontend/app/*` as migration sources

### Exit Criteria

- the Vite app owns route definitions directly
- the desktop shell no longer imports Next page entrypoints as routes
- route composition has one active owner

## Phase 4: Migrate Screens Into Vite-Owned Modules

### Goal

Move screen ownership out of the Next app tree and into Vite-owned modules.

### Status

Completed on `2026-03-28`.

### Tasks

- Identify the route screens currently imported from `frontend/app`.
- Move or split them into Vite-owned feature modules under `frontend/src`.
- Keep shared UI and feature logic framework-agnostic during the move.
- Replace any lingering Next-only wrappers with plain React components.
- Prioritize heavily used routes first:
  - dashboard
  - inventory
  - jobs
  - outputs
  - replay
  - convert
- Update imports so the Vite route tree uses only Vite-owned modules.

### Implemented In This Phase

- Moved the route-facing screen modules from `frontend/app` into
  `frontend/src/features`.
- Kept the Next page wrappers in place, but rewired them to import the moved
  feature screens from `src/features`.
- Updated the Vite route tree to depend only on feature modules under
  `frontend/src`.
- Preserved the current hybrid migration state by keeping the Next routes thin
  while making Vite the owner of both route composition and screen imports.

### Likely Files

- `frontend/app/**/*`
- `frontend/src/routes/*`
- `frontend/src/features/*` or similar new modules
- `frontend/src/App.tsx`

### Validation

- `npm run typecheck`
- `npm test`
- `npm run desktop:build`
- `npm run build`

### Exit Criteria

- Vite route screens no longer depend on Next page modules
- screen composition is owned from `frontend/src`
- framework-specific wrappers are minimized

## Phase 5: Desktop Startup And Asset-Ingestion Cleanup

### Goal

Remove the remaining legacy web assumptions from desktop behavior.

### Status

Completed on `2026-03-28`.

### Tasks

- Remove the hidden file-input fallback from the desktop inventory add-files
  flow.
- Ensure desktop file selection always produces path registration.
- Treat native dialog failure as a real desktop/runtime failure, not a signal
  to upload bytes.
- Split desktop path registration and optional web upload into explicit
  ingestion paths.
- Remove desktop dependence on:
  - `/assets/upload`
  - `/assets/register-dialog`
- Consolidate duplicated result-formatting and progress logic between upload and
  register flows where appropriate.

### Implemented In This Phase

- Changed the native dialog helpers to distinguish:
  - selection
  - cancellation
  - runtime failure
- Made inventory file add capability-driven:
  - desktop runtime uses native path selection plus `/assets/register`
  - browser runtime uses file upload explicitly
- Removed the silent desktop fallback from native file selection to browser
  upload.
- Surfaced native dialog failures as real inventory notices/tests instead of
  swallowing them.
- Removed the unused `/assets/register-dialog` frontend API helper.

### Likely Files

- `frontend/app/inventory/inventory-upload-dialog.tsx`
- `frontend/app/inventory/inventory-scan-dialog.tsx`
- `frontend/src/lib/native-dialogs.ts`
- `frontend/src/hooks/use-register-asset-paths.ts`
- `frontend/src/hooks/use-upload-assets.ts`
- `frontend/src/lib/api.ts`

### Validation

- `npm test`
- `npm run desktop:build`
- manual `npm run tauri:dev` checks for:
  - add files
  - scan directory
  - dialog cancel
  - dialog failure handling

### Exit Criteria

- desktop ingestion is path-based only
- desktop mode no longer silently falls back to browser upload
- platform-specific ingestion behavior is explicit

## Phase 6: Retire The Next App Surface

### Goal

Remove the Next app as an active runtime and clean up supporting drift.

### Status

Completed on `2026-03-28`.

### Tasks

- Remove or archive `frontend/app` once screen migration is complete.
- Remove Next-specific app shell composition that is no longer used.
- Remove Next-specific routing abstractions that are no longer needed.
- Simplify build scripts, typecheck assumptions, and docs around the single
  Vite runtime.
- Decide whether a web build is still required:
  - if yes, serve the Vite app for web too
  - if no, remove web-runtime-only scaffolding
- Update README and design docs to describe the single-runtime model.

### Implemented In This Phase

- Deleted the old `frontend/app` Next App Router tree.
- Removed the unused Next build config and moved the favicon into `public/`.
- Collapsed `frontend/src/lib/app-routing.tsx` into the single React Router
  implementation and removed the alias-based test/build shim.
- Switched the active `dev`, `build`, `start`, and `typecheck` scripts to the
  Vite/TypeScript toolchain.
- Left some Next-oriented package/tooling dependencies in place temporarily,
  but they are no longer part of the active runtime path.

### Likely Files

- `frontend/app/**/*`
- `frontend/next.config.mjs`
- `frontend/package.json`
- `frontend/src/lib/app-routing.tsx`
- `frontend/README.md`

### Exit Criteria

- Next App Router is no longer an active app runtime
- frontend build/runtime docs describe one application model
- Vite is the single frontend runtime in practice

## Phase 7: Validation, Docs, And Closeout

### Goal

Finish the migration with stable validation and updated tracking docs.

### Tasks

- Update `frontend/design/current-state.md` with the final implementation
  state.
- Update `frontend/design/parity-checklist.md` to reflect the Vite-first
  runtime.
- Update `frontend/README.md` for:
  - local development
  - Tauri development
  - desktop packaging
  - runtime expectations
- Run full validation:
  - `npm run typecheck`
  - `npm test`
  - `npm run build`
  - `npm run desktop:build`
  - `cargo check --manifest-path frontend/src-tauri/Cargo.toml`
- Run manual desktop smoke checks across core routes and startup/runtime flows.
- Record any remaining rough edges that should become separate follow-up work.

### Exit Criteria

- docs describe the single Vite runtime clearly
- current-state tracking matches the real codebase
- the Vite/Tauri frontend is the clear steady-state architecture

## Recommended Delivery Order

1. runtime boundary
2. non-blocking startup
3. route ownership separation
4. screen migration into Vite-owned modules
5. asset-ingestion cleanup
6. retire Next runtime
7. validation and docs

## Tracking Rules

- update `frontend/design/current-state.md` after each completed phase
- keep phase status explicit: `pending`, `in progress`, or `completed`
- note where Next-specific code still remains after each phase
- do not leave migration shims undocumented
