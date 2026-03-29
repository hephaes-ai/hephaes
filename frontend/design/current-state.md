# Frontend Current State

## Purpose

This document is the working implementation snapshot for the frontend
Vite/Tauri migration.

It is meant to help implementation agents answer:

- what the active frontend runtime looks like now
- which migration phases are already complete
- where cleanup work still remains
- which files matter most for final closeout

## Snapshot

As of `2026-03-28`, `frontend/` now has one active application surface:

- a Vite-powered React app under `frontend/src`
- a Tauri host under `frontend/src-tauri`

The old Next App Router tree under `frontend/app` has been removed.

## Current Architecture Reality

The frontend is no longer in a hybrid Next/Vite runtime state.

Current ownership is:

- app entrypoint: `frontend/src/main.tsx`
- app shell: `frontend/src/App.tsx`
- route tree: `frontend/src/routes`
- route-facing screens: `frontend/src/features`
- runtime boundary: `frontend/src/lib/backend-runtime.ts`
- routing abstraction: `frontend/src/lib/app-routing.tsx`
- desktop host and sidecar lifecycle: `frontend/src-tauri`

## What Already Works

The following migration phases are complete:

- explicit frontend runtime contract with mode, status, and capabilities
- non-blocking desktop startup
- Vite-owned route composition
- Vite-owned route-facing screen modules
- desktop path-based asset ingestion with no silent browser-upload fallback
- removal of the Next App Router runtime surface

Current validation baseline:

- `npm test` passes
- `npm run typecheck` passes
- `npm run build` passes
- `npm run desktop:build` passes
- `cargo check --manifest-path frontend/src-tauri/Cargo.toml` passes

## What Is Still Incomplete

## 1. Some Next-oriented tooling dependencies still remain

The active runtime no longer depends on Next, but some tooling/dependency
footprints are still present in files such as:

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/eslint.config.mjs`

These are no longer part of the active runtime path, but they should be
cleaned up deliberately rather than left ambiguous.

## 2. The desktop bundle is still large

`npm run build` and `npm run desktop:build` still emit the large-chunk warning
for the main bundle. That is not blocking the migration, but it remains a
follow-up quality issue.

## Current State By Area

### Desktop Runtime

Current state:

- runtime snapshot is explicit and capability-driven
- Tauri startup is non-blocking
- the startup screen stays mounted until runtime readiness or early failure
- sidecar lifecycle updates flow into React through the runtime store
- desktop development now defaults to an external backend at
  `http://127.0.0.1:8000`
- the recommended backend dev launcher is `frontend/package.json` ->
  `npm run backend:dev`, which uses a clean repo-local `.dev/backend` data root
- packaged desktop builds still stage and launch the backend sidecar

Primary files:

- `frontend/src-tauri/src/lib.rs`
- `frontend/src/bootstrap-app.tsx`
- `frontend/src/lib/backend-runtime.ts`
- `frontend/src/hooks/use-desktop-backend-runtime.ts`
- `frontend/scripts/run-tauri-dev.mjs`

### Routing And Screens

Current state:

- route composition lives under `frontend/src/routes`
- route-facing screens live under `frontend/src/features`
- `frontend/src/lib/app-routing.tsx` is the single routing abstraction
- `frontend/src/App.tsx` is now a thin shell around the Vite route tree

Primary files:

- `frontend/src/App.tsx`
- `frontend/src/routes/**/*`
- `frontend/src/features/**/*`
- `frontend/src/lib/app-routing.tsx`

### Asset Ingestion

Current state:

- desktop add-files uses native path selection plus `/assets/register`
- desktop scan-directory uses native directory selection plus
  `/assets/scan-directory`
- browser upload remains capability-driven instead of being a hidden desktop
  fallback
- native dialog failures surface as inventory notices

Primary files:

- `frontend/src/features/inventory/inventory-upload-dialog.tsx`
- `frontend/src/features/inventory/inventory-scan-dialog.tsx`
- `frontend/src/hooks/use-register-asset-paths.ts`
- `frontend/src/hooks/use-upload-assets.ts`
- `frontend/src/lib/native-dialogs.ts`
- `frontend/src/lib/api.ts`

### Build Surface

Current state:

- `dev` uses Vite
- `build` uses Vite
- `start` uses `vite preview`
- `typecheck` is plain TypeScript, not Next typegen
- desktop build aliases resolve through the same Vite runtime

Primary files:

- `frontend/package.json`
- `frontend/vite.config.ts`
- `frontend/tsconfig.json`
- `frontend/tsconfig.typecheck.json`

## Main Files To Watch

### Runtime Boundary

- `frontend/src-tauri/src/lib.rs`
- `frontend/src/bootstrap-app.tsx`
- `frontend/src/lib/backend-runtime.ts`

### Route And Feature Ownership

- `frontend/src/App.tsx`
- `frontend/src/routes/**/*`
- `frontend/src/features/**/*`
- `frontend/src/lib/app-routing.tsx`

### Asset Ingestion

- `frontend/src/features/inventory/inventory-upload-dialog.tsx`
- `frontend/src/features/inventory/inventory-scan-dialog.tsx`
- `frontend/src/lib/native-dialogs.ts`
- `frontend/src/hooks/use-register-asset-paths.ts`
- `frontend/src/hooks/use-upload-assets.ts`

### Final Cleanup

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/eslint.config.mjs`
- `frontend/README.md`
- `frontend/design/architecture.md`
- `frontend/design/implementation.md`

## Phase Tracker

This tracker follows `frontend/design/implementation.md`.

Current phase status:

- Phase 1 completed: define and stabilize the runtime boundary
- Phase 2 completed: make desktop startup non-blocking and explicit
- Phase 3 completed: separate route ownership from the Next app tree
- Phase 4 completed: migrate screens into Vite-owned route modules
- Phase 5 completed: remove legacy web assumptions from asset ingestion
- Phase 6 completed: retire the Next app surface and clean up build/runtime drift
- Phase 7 completed: validate, document, and close the migration

## Migration Risks To Watch

- final cleanup should not reintroduce runtime-specific routing abstractions
- tooling cleanup should not break the validated Vite/Tauri build path
- future desktop work should use runtime capabilities instead of platform checks
- bundle-size follow-up work should stay separate from migration closeout

## Working Definition Of Progress

This migration should be considered fully complete when:

- the docs describe the Vite/Tauri runtime clearly
- remaining Next-oriented tooling drift is either removed or explicitly
  justified
- the current-state tracker matches the real codebase
- any remaining bundle-size warning is tracked as follow-up rather than mixed
  into runtime migration work
