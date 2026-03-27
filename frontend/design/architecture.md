# Backend Sidecar Architecture

## Summary

This document describes the next desktop architecture for `frontend/`.

The frontend migration is complete enough to treat the Tauri shell as the
primary app container. The next step is to package the FastAPI backend as a
local sidecar so the app can launch from a single executable and fully manage
its own backend lifecycle.

## Scope

In scope:

- bundle the FastAPI backend with the Tauri app as a local sidecar
- let Tauri launch, monitor, and stop the backend process
- move backend storage into desktop app-managed directories
- provide the resolved backend base URL to the frontend at runtime
- keep the current REST and WebSocket API contract intact
- replace desktop-only native picker behavior with Tauri-native dialogs where
  needed

Out of scope:

- rewriting backend APIs into Rust commands
- turning the backend into a long-running system service outside the app
- redesigning the data model, jobs model, or database schema
- changing core frontend routes or feature behavior unless sidecar support
  requires it

## Current State

Today the desktop app already has:

- a working Tauri shell in `frontend/src-tauri`
- a React + Vite frontend in `frontend/src`
- runtime backend URL support in `frontend/src/lib/api.ts`
- a desktop build and dev flow that assumes a separately started backend

The backend is still standalone and still assumes source-tree-relative storage
defaults. It also contains desktop-specific file dialog logic implemented with
`tkinter` and AppleScript, which is not a good long-term fit for a bundled
desktop app.

## Target Architecture

### High-Level Design

- Tauri remains the native host, installer target, and process supervisor.
- React + Vite remains the frontend runtime.
- FastAPI stays a separate process, but is bundled inside the desktop app.
- Rust owns sidecar startup, shutdown, health checks, configuration injection,
  and error reporting.
- The frontend continues to talk to the backend over loopback HTTP and
  WebSocket using a runtime-provided base URL.

## Runtime Topology

```text
+-------------------------------+
| Hephaes desktop bundle        |
|  - Tauri host                |
|  - React/Vite frontend       |
|  - bundled backend binary    |
+---------------+---------------+
                |
                v
+-------------------------------+
| Tauri runtime                 |
|  - resolves app data paths    |
|  - picks backend port         |
|  - spawns sidecar             |
|  - waits for /health          |
|  - exposes backend base URL   |
+---------------+---------------+
                |
                v
+-------------------------------+
| FastAPI backend sidecar       |
|  - binds 127.0.0.1:<port>     |
|  - uses app-local db/storage  |
|  - serves HTTP + WebSocket    |
+-------------------------------+
```

## Startup Sequence

1. The user launches the desktop app.
2. Tauri resolves app-local paths for data, raw assets, outputs, and logs.
3. Tauri picks a local backend port.
4. Tauri starts the bundled backend binary with env vars for host, port, and
   storage paths.
5. Tauri polls `GET /health` until the backend is ready or startup times out.
6. Tauri publishes the resolved backend base URL to the frontend runtime.
7. The main window becomes visible and the React app boots normally.

## Shutdown Sequence

1. The app begins exit or window-close handling.
2. Tauri signals the backend child process to stop.
3. Tauri waits briefly for graceful shutdown.
4. Tauri force-kills the child only if it does not exit cleanly.
5. Logs remain in the desktop log directory for debugging failed launches.

## Process Ownership

Tauri is the single owner of backend lifecycle in packaged mode.

- the backend should never choose its own storage root in packaged mode
- the backend should never depend on repository-relative paths in packaged mode
- the frontend should never hardcode `http://127.0.0.1:8000` in packaged mode
- the backend should bind only to loopback

## Backend Runtime Contract

The backend sidecar should accept configuration entirely through environment
variables or CLI flags provided by Tauri.

Required runtime inputs:

- `HEPHAES_BACKEND_HOST`
- `HEPHAES_BACKEND_PORT`
- `HEPHAES_BACKEND_DATA_DIR`
- `HEPHAES_BACKEND_RAW_DATA_DIR`
- `HEPHAES_BACKEND_OUTPUTS_DIR`
- `HEPHAES_BACKEND_DB_PATH`
- `HEPHAES_BACKEND_LOG_DIR`
- `HEPHAES_DESKTOP_MODE=1`

Recommended behavior:

- keep all current API routes unchanged
- keep all current WebSocket routes unchanged
- create missing directories on startup
- fail fast with clear logs if paths are invalid or unwritable

## Frontend Runtime Contract

The frontend should treat the backend URL as runtime state provided by Tauri,
not as a build-time constant.

Packaged mode:

- Tauri provides `baseUrl`
- frontend sets `globalThis.__HEPHAES_BACKEND_BASE_URL__` before React renders
- frontend shows a startup or failure view if the sidecar never becomes healthy

Development mode:

- retain `VITE_BACKEND_BASE_URL` for local debugging
- allow bypassing the sidecar so frontend and backend can still be developed
  independently

## Storage Model

Desktop storage should live under app-managed directories instead of the source
tree.

Recommended layout:

```text
AppData/
  backend/
    app.db
    raw/
    outputs/
    logs/
```

This keeps the packaged app self-contained and preserves user data across app
upgrades.

## Native Integration Boundaries

Tauri-native responsibilities:

- process launch and supervision
- app data path resolution
- splash screen or hidden-window startup experience
- native file and directory selection
- failure reporting for sidecar startup

Backend responsibilities:

- indexing
- conversion
- job orchestration
- output generation
- replay and visualization APIs

Frontend responsibilities:

- route rendering
- user interaction
- backend polling and mutations
- desktop boot state presentation

## Packaging Strategy

The backend should be packaged as a standalone executable first and only then
added as a Tauri sidecar.

Recommended path:

- first prove a frozen backend binary in a debug-friendly `onedir` layout
- once stable, switch to a single bundled executable if startup time and
  dependency behavior remain acceptable

This reduces sidecar-debug complexity and keeps backend packaging problems
isolated from Tauri integration.

## Security And Permissions

- the backend sidecar should be the only executable Tauri is allowed to spawn
- the backend should bind to `127.0.0.1`, not a public interface
- the frontend should only learn the chosen loopback URL from Tauri
- the packaged app should not require repository access to run

## Risks

- Python packaging may be the longest and most failure-prone part of this work
- backend dependencies such as `rerun-sdk` and the local `hephaes` package may
  require explicit packaging hooks
- repo-relative defaults in backend settings can leak into packaged mode if not
  removed cleanly
- current backend dialog flows are not a good fit for a bundled desktop app
- replay and WebSocket behavior still need packaged-app validation

## Success Criteria

The sidecar architecture is complete when:

- launching the desktop app also launches a working backend automatically
- no separate terminal command is required for normal app usage
- the backend persists data in app-managed directories
- the frontend receives the backend URL from Tauri at runtime
- packaged builds can perform inventory, convert, outputs, and replay flows
- backend startup failures produce a clear user-visible error state and useful
  logs
