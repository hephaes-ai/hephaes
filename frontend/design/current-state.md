# Frontend Current State

## Purpose

This document is the working implementation snapshot for the frontend runtime
migration.

It is meant to help implementation agents answer:

- what the frontend actually looks like today
- which parts still belong to the old Next-based structure
- which parts already belong to the Vite/Tauri structure
- where the migration is incomplete
- which implementation phase is currently active

This tracker is for the full Vite-first frontend migration, not just a narrow
desktop bugfix.

## Snapshot

As of `2026-03-28`, the frontend currently has two overlapping runtime
surfaces.

### Vite/Tauri Surface

Implemented today:

- Vite app entrypoint in `frontend/src/main.tsx`
- desktop bootstrap layer in `frontend/src/bootstrap-app.tsx`
- desktop app shell in `frontend/src/App.tsx`
- React Router runtime in `frontend/src/lib/app-routing.react-router.tsx`
- Tauri shell and backend sidecar lifecycle in `frontend/src-tauri`
- desktop-native dialog helpers in `frontend/src/lib/native-dialogs.ts`

### Next Surface

Still present today:

- Next App Router tree in `frontend/app`
- Next layout in `frontend/app/layout.tsx`
- Next routing helpers in `frontend/src/lib/app-routing.tsx`
- Next build and type generation scripts in `frontend/package.json`

### Shared Feature Code Situation

Today the desktop app still imports route modules from the Next app tree, so
the Vite/Tauri app is not fully independent yet.

## Current Architecture Reality

The current frontend is not:

- fully Next
- fully Vite

It is a hybrid migration state.

The desktop shell is the most important active runtime, but it still depends on
the old Next app structure for route modules and screen ownership.

## What Already Works

The baseline engineering health is good:

- `npm run typecheck` passes
- `npm test` passes
- `npm run build` passes
- `npm run desktop:build` passes
- `cargo check --manifest-path frontend/src-tauri/Cargo.toml` passes

The desktop runtime also already has:

- backend sidecar startup and shutdown logic
- runtime backend URL support
- startup/failure UI in the frontend
- native file and directory dialogs
- desktop path-based asset registration support

## What Is Still Incomplete

## 1. Two app runtimes still exist

The repo still carries both:

- Next App Router as an app surface
- Vite + React Router as another app surface

This is the main structural migration gap.

## 2. Route ownership still depends on Next modules

The Vite app now owns the route tree from `frontend/src/routes`, but the
underlying screen modules still live under `frontend/app`.

That means route composition is no longer owned by Next page entrypoints, but
screen ownership is still not fully Vite-native yet.

## 3. Runtime assumptions are still mixed

Desktop-specific runtime behavior exists, but some assumptions still reflect
the old web model:

- desktop asset intake can still fall back to browser upload behavior

## 4. Feature ownership is not yet Vite-native

Many major screens still live under `frontend/app`, including:

- inventory
- dashboard
- outputs
- jobs
- replay
- convert

That means the route screens are not yet cleanly owned from `frontend/src`.

## 5. Large screens remain hard to migrate

Some route modules are very large, especially conversion authoring.

This increases migration risk because:

- route migration
- runtime cleanup
- feature cleanup

can become tangled if not phased carefully.

## Current State By Area

### Desktop Runtime

Current state:

- Tauri sidecar exists
- runtime snapshot contract now includes explicit mode, status, and
  capabilities
- frontend bootstrap exists
- startup is now non-blocking from the Rust side
- the startup screen stays mounted until the runtime reaches `ready` or an
  early `failed` / `stopped` state

Primary files:

- `frontend/src-tauri/src/lib.rs`
- `frontend/src/bootstrap-app.tsx`
- `frontend/src/lib/backend-runtime.ts`

### Routing

Current state:

- React Router is active in the Vite app
- Next App Router still exists
- route ownership is now centered in `frontend/src/routes`
- screen modules are still imported from `frontend/app`
- feature code can now read runtime mode/capabilities from one normalized
  frontend runtime source

Primary files:

- `frontend/src/App.tsx`
- `frontend/src/lib/app-routing.react-router.tsx`
- `frontend/src/lib/app-routing.tsx`
- `frontend/app/**/*`

### Asset Ingestion

Current state:

- desktop native path-selection exists
- path registration exists
- directory scan exists
- browser upload fallback still exists in desktop add-files flow
- runtime capabilities now distinguish desktop path registration from browser
  upload, but the inventory flows do not fully enforce that split yet

Primary files:

- `frontend/app/inventory/inventory-upload-dialog.tsx`
- `frontend/app/inventory/inventory-scan-dialog.tsx`
- `frontend/src/lib/native-dialogs.ts`
- `frontend/src/hooks/use-register-asset-paths.ts`
- `frontend/src/hooks/use-upload-assets.ts`

### Build Surface

Current state:

- Next build remains active
- Vite desktop build remains active
- package scripts still describe both worlds

Primary files:

- `frontend/package.json`
- `frontend/next.config.mjs`
- `frontend/vite.config.ts`

## Main Files To Watch

### Runtime Boundary

- `frontend/src-tauri/src/lib.rs`
- `frontend/src/bootstrap-app.tsx`
- `frontend/src/lib/backend-runtime.ts`
- `frontend/src/hooks/use-desktop-backend-runtime.ts`

### Route Ownership

- `frontend/src/App.tsx`
- `frontend/src/lib/app-routing.react-router.tsx`
- `frontend/src/lib/app-routing.tsx`
- `frontend/app/**/*`
- future `frontend/src/routes/**/*`

### Asset Ingestion

- `frontend/app/inventory/inventory-upload-dialog.tsx`
- `frontend/app/inventory/inventory-scan-dialog.tsx`
- `frontend/src/lib/native-dialogs.ts`
- `frontend/src/hooks/use-register-asset-paths.ts`
- `frontend/src/hooks/use-upload-assets.ts`
- `frontend/src/lib/api.ts`

### Migration Cleanup

- `frontend/package.json`
- `frontend/README.md`
- `frontend/next.config.mjs`
- `frontend/vite.config.ts`

## Phase Tracker

This tracker follows `frontend/design/implementation.md`.

Current phase status:

- Phase 1 completed: define and stabilize the runtime boundary
- Phase 2 completed: make desktop startup non-blocking and explicit
- Phase 3 completed: separate route ownership from the Next app tree
- Phase 4 pending: migrate screens into Vite-owned route modules
- Phase 5 pending: remove legacy web assumptions from asset ingestion
- Phase 6 pending: retire the Next app surface and clean up build/runtime drift
- Phase 7 pending: validate, document, and close the migration

## Migration Risks To Watch

- route migration should not regress the newly normalized runtime contract
- asset-ingestion cleanup should consume runtime capabilities instead of adding
  new platform checks in feature components
- route migration should not reintroduce blocking boot assumptions into screen
  composition
- screen migration should not pull route ownership back into `frontend/app`

- route migration may stall if large screen modules are not split carefully
- desktop startup fixes may be harder to validate if route/runtime cleanup is
  mixed into one large change
- browser upload behavior may still be implicitly relied on by some flows
- Next-based typecheck/build assumptions may linger after route ownership moves

## Working Definition Of Progress

This migration should be considered substantially complete when:

- the Vite app owns routing and screen composition
- Tauri startup behavior is explicit and non-blocking
- desktop asset ingestion is path-based only
- Next App Router is no longer an active frontend runtime
- `current-state.md` accurately reflects the migration state after each phase
