# Frontend Tauri Architecture

## Summary

This document describes the phase 1 desktop architecture for `frontend/`.

The goal of phase 1 is to migrate the current Next.js frontend into a Tauri app
while keeping the FastAPI backend standalone. The frontend will continue to talk
to the backend over HTTP and WebSocket on localhost. Backend sidecarring,
desktop-native file dialogs, and backend packaging are explicitly deferred to a
later phase.

## Scope

In scope:

- replace Next.js with a client-rendered React app inside `frontend/`
- add a Tauri shell in `frontend/src-tauri`
- preserve the current UI behavior, routes, and backend API contract
- keep replay and visualization flows working against the existing backend
- keep the backend configurable through a runtime base URL

Out of scope:

- bundling or sidecarring FastAPI
- rewriting backend APIs into Tauri commands
- changing backend storage, job execution, or database behavior
- replacing backend-native file picking or upload flows unless required for
  parity

## Current State

Today the frontend is a Next.js App Router app with:

- route wrappers under `frontend/app`
- client-heavy feature pages under `frontend/app/**/**-page.tsx`
- shared UI logic under `frontend/components`, `frontend/hooks`, and
  `frontend/lib`
- backend access through `frontend/lib/api.ts`
- desktop backend base URL configured through a runtime value or
  `VITE_BACKEND_BASE_URL`
- legacy Next.js fallback still available through `NEXT_PUBLIC_BACKEND_BASE_URL`

This is already close to a SPA architecture. Most of the migration cost is in:

- replacing Next router primitives
- removing server redirects and route wrappers
- switching build tooling from Next to Vite
- adding the Tauri shell and desktop packaging flow

## Target Architecture

### High-Level Design

- Tauri provides the native desktop shell, window lifecycle, and app packaging.
- React + Vite provides the frontend runtime.
- React Router replaces Next App Router.
- The FastAPI backend remains an external process during phase 1.
- The frontend continues to call the backend on loopback HTTP and WebSocket.

## Runtime Topology

```text
+---------------------------+
| Tauri desktop shell       |
|  - native window          |
|  - app packaging          |
|  - no backend sidecar yet |
+-------------+-------------+
              |
              v
+---------------------------+
| React + Vite frontend     |
|  - routes                 |
|  - SWR/cache/hooks        |
|  - rerun web viewer       |
+-------------+-------------+
              |
              v
+---------------------------+
| FastAPI backend           |
|  http://127.0.0.1:8000    |
|  ws://127.0.0.1:8000      |
|  standalone process       |
+---------------------------+
```

## Routing Model

The Tauri app will ship as a SPA. Route resolution moves from file-based Next
routes to explicit client routes.

Target route mapping:

- `/` -> redirect to `/dashboard`
- `/dashboard` -> dashboard
- `/inventory` -> inventory
- `/assets/:assetId` -> asset detail
- `/jobs` -> jobs list
- `/jobs/:jobId` -> job detail
- `/outputs` -> outputs list
- `/outputs/:outputId` -> output detail
- `/replay` -> visualization/replay
- `/visualize` -> redirect to `/replay`
- `/convert` -> client bootstrap route that decides between `/convert/new` and
  `/convert/use`
- `/convert/new` -> authoring create mode
- `/convert/use` -> authoring use mode

## Backend Contract

Phase 1 intentionally preserves the backend boundary:

- all current REST endpoints stay unchanged
- all current WebSocket endpoints stay unchanged
- the frontend still resolves asset/output URLs through the backend
- backend health remains the source of truth for app availability

The only required frontend API change is configuration:

- replace `NEXT_PUBLIC_BACKEND_BASE_URL` with a Vite-compatible config path
- keep a default backend URL of `http://127.0.0.1:8000`
- allow the desktop app to override the backend base URL at runtime or build
  time

## Directory Layout

Planned end state for `frontend/`:

```text
frontend/
  design/
    architecture.md
    implementation.md
  public/
  src/
    app/
    components/
    hooks/
    lib/
    routes/
    main.tsx
  src-tauri/
    src/
    Cargo.toml
    tauri.conf.json
  index.html
  package.json
  vite.config.ts
  tsconfig.json
```

Notes:

- `frontend/app` from Next is retired after migration.
- shared code should be moved, not rewritten, wherever possible.
- route-specific UI can stay grouped by feature to minimize churn.

## Design Principles

- preserve behavior first, improve architecture second
- keep the backend contract stable during the frontend migration
- prefer client routing and local state changes over server-derived route logic
- minimize Tauri-specific code in shared UI modules
- isolate Tauri integration to bootstrap, config, and later desktop-only affordances

## Risks

- replay and Rerun viewer behavior inside the Tauri webview may need small
  adjustments
- browser-upload behavior may feel awkward in a desktop shell, even if it still
  works
- the `/convert` bootstrap flow currently depends on request-time backend fetches
  and must be rewritten as a client flow
- environment configuration needs to move off Next-specific conventions

## Success Criteria

Phase 1 is complete when:

- the desktop app launches through Tauri
- all major routes render through React Router
- the frontend can talk to a separately started FastAPI backend
- inventory, jobs, outputs, convert, and replay work without Next.js
- `frontend/` can be built and packaged as a desktop app without bundling the
  backend
