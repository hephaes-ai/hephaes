# Frontend Runtime Architecture

## Summary

This document defines the target frontend architecture for `frontend/`.

The target is:

- one Vite-powered React app
- one routing model
- one runtime abstraction layer
- Tauri as the native desktop host

The Next.js App Router tree should not remain as a second application surface.
It is currently useful as a migration source, but it should not remain part of
the steady-state architecture.

## Problem Statement

The frontend currently contains two overlapping app models:

- a Next.js app under `frontend/app`
- a Vite + React Router desktop app under `frontend/src`

The desktop shell currently imports and reuses page modules from the Next app
while swapping runtime behavior with aliases and shims.

That creates several problems:

- two routing systems must be kept in sync
- platform behavior is split across Next assumptions and desktop assumptions
- startup and runtime behavior are harder to reason about
- desktop-specific work can be blocked by web-framework coupling
- large screens are harder to refactor because they serve two runtimes at once

## Architecture Goal

The long-term frontend architecture should be:

- `frontend/src` is the single app runtime
- Vite is the single frontend build tool
- React Router is the single routing layer
- Tauri hosts the Vite app for desktop
- platform-specific behavior is abstracted behind a small runtime boundary

If a browser build remains necessary later, it should use the same Vite app and
the same route definitions rather than a separate Next application tree.

## In Scope

- collapsing the app surface to one Vite app
- removing Next-specific runtime assumptions from feature code
- unifying routing and app composition under React Router
- keeping a clean runtime boundary for:
  - desktop startup
  - backend runtime status
  - native dialogs
  - platform capabilities
- migrating startup and asset-ingestion flows to desktop-native behavior

## Out Of Scope

- rewriting the backend into Rust commands
- redesigning product features
- a full visual redesign
- converting the entire app into Tauri-specific Rust UI

## Design Principles

### 1. One application surface

The repo should not maintain both:

- a Next application tree as an app runtime
- a Vite application tree as another app runtime

There should be one source of truth for:

- routes
- app providers
- app shell
- runtime state

### 2. Platform concerns belong at the boundary

Feature components should not care whether they are running:

- in Tauri
- against an external loopback backend
- in a browser-only environment

They should read this through a narrow runtime interface instead of framework-
or platform-specific checks scattered across the app.

### 3. Desktop behavior must be explicit

For desktop mode:

- startup is runtime-driven and visible
- native dialogs are explicit capabilities
- asset ingestion is path-based
- browser upload behavior is not an invisible fallback

### 4. Route modules should be framework-agnostic

Feature screens should be plain React components.

Routing concerns should live in the Vite app shell, not in duplicated
framework-specific wrappers.

### 5. Migration should end in deletion

The Next app may temporarily remain as a migration source, but the architecture
is only complete when Next-specific app composition is deleted rather than left
as parallel infrastructure.

## Target Topology

```text
frontend/
  src/
    main.tsx
    App.tsx
    routes/
    components/
    hooks/
    lib/
  src-tauri/
    src/lib.rs
  public/
```

Target responsibilities:

- `src/main.tsx`
  - single frontend entrypoint
- `src/App.tsx`
  - app providers
  - app shell
  - router
- `src/routes/*`
  - route definitions
  - route wrappers
- `src/components/*`
  - reusable UI and presentation
- `src/hooks/*`
  - feature orchestration
- `src/lib/*`
  - API, runtime, navigation, shared utilities
- `src-tauri/*`
  - desktop host and sidecar lifecycle

## Target Routing Model

React Router should be the single routing system.

The route tree should live in the Vite app, and it should own:

- `/dashboard`
- `/inventory`
- `/assets/:assetId`
- `/jobs`
- `/jobs/:jobId`
- `/outputs`
- `/outputs/:outputId`
- `/replay`
- `/convert`
- `/convert/new`
- `/convert/use`
- redirects such as `/` and `/visualize`

Next App Router page modules should not remain as the route source after the
migration.

## Target Runtime Boundary

The runtime boundary should expose explicit mode and capabilities.

Recommended model:

```ts
type FrontendMode = "desktop-sidecar" | "desktop-external" | "web"
type RuntimeStatus = "loading" | "ready" | "failed" | "stopped"

interface FrontendCapabilities {
  nativeFileDialog: boolean
  nativeDirectoryDialog: boolean
  pathAssetRegistration: boolean
  browserUpload: boolean
}

interface FrontendRuntimeSnapshot {
  mode: FrontendMode
  status: RuntimeStatus
  baseUrl: string
  error?: string | null
  backendLogDir?: string | null
  desktopLogDir?: string | null
  capabilities: FrontendCapabilities
}
```

This runtime boundary should be the single place that translates:

- Tauri events
- Tauri commands
- browser mode defaults
- development overrides

## Target Desktop Startup Flow

1. Tauri launches the webview quickly.
2. The frontend renders a startup screen immediately.
3. Rust starts the backend sidecar asynchronously.
4. Rust emits runtime updates.
5. React transitions through:
   - loading -> ready
   - loading -> failed
   - ready -> stopped

The important architectural point is:

- React owns startup presentation
- Rust owns process lifecycle
- neither side should assume the other is blocking invisibly

## Target Asset Ingestion Flow

### Desktop

Desktop ingestion should be:

1. open native file or directory dialog
2. receive local filesystem paths
3. call path-based backend endpoints
4. display path-based results and failures

Desktop should use:

- `/assets/register`
- `/assets/scan-directory`

Desktop should not silently use:

- browser `<input type="file">`
- `/assets/upload`
- `/assets/register-dialog`

### Web

If browser upload remains supported, it should be:

- explicit
- capability-driven
- isolated from desktop ingestion UI

## Module Boundaries

### Desktop host

Responsible for:

- sidecar startup and shutdown
- runtime status emission
- desktop log/data paths
- Tauri-native capabilities

Anchor today:

- `frontend/src-tauri/src/lib.rs`

### Frontend runtime layer

Responsible for:

- normalized runtime snapshot
- capability exposure
- startup-state subscription
- frontend bootstrap decisions

Anchor today:

- `frontend/src/lib/backend-runtime.ts`
- `frontend/src/bootstrap-app.tsx`
- `frontend/src/hooks/use-desktop-backend-runtime.ts`

### Routing and app composition

Responsible for:

- route definitions
- shell layout
- provider composition
- framework-independent screen rendering

Anchor today:

- `frontend/src/App.tsx`
- `frontend/src/components/app-shell.tsx`
- `frontend/src/components/app-providers.tsx`

### Asset ingestion layer

Responsible for:

- choosing ingestion strategy by capability
- native dialogs in desktop mode
- path registration
- optional browser upload in web mode

Anchor today:

- `frontend/src/lib/native-dialogs.ts`
- `frontend/src/hooks/use-register-asset-paths.ts`
- `frontend/src/hooks/use-upload-assets.ts`
- `frontend/app/inventory/inventory-upload-dialog.tsx`
- `frontend/app/inventory/inventory-scan-dialog.tsx`

## Migration Boundary

During migration, the Next app may temporarily remain as a source of feature
components, but the architecture is only complete when:

- route ownership has moved fully into the Vite app
- feature modules no longer depend on Next navigation APIs
- `frontend/app` is no longer an active app runtime
- build, typecheck, and desktop validation no longer rely on the Next app tree

## Success Criteria

This architecture is complete when:

- Vite is the only frontend runtime
- React Router is the only route system
- Tauri startup and desktop runtime behavior are explicit and testable
- desktop asset ingestion is path-based and native
- Next App Router is no longer an active application surface
- feature code no longer depends on mixed web and desktop assumptions
