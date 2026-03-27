# Backend Sidecar Implementation Plan

## Goal

Package the FastAPI backend into the Tauri app so a user can launch one desktop
application and have the full product working without starting a separate
backend process manually.

## Guiding Constraints

- keep the current backend API contract intact during the sidecar migration
- preserve the existing React + Vite desktop frontend
- keep development workflows usable while packaged mode is being added
- ship in phases where each checkpoint can be validated independently
- finish each phase with passing validation before moving to the next one

## Phase 0: Packaging Spike And Baseline

Tasks:

- choose the initial backend freezing path and prove it on one platform first
- add a desktop backend entrypoint that starts FastAPI with host and port
  supplied from runtime config
- verify the backend can run outside the repo layout after packaging
- keep this phase isolated from Tauri so backend packaging bugs are easier to
  debug

Deliverable:

- a standalone packaged backend executable that answers `GET /health`

Validation:

- launch the packaged backend directly from the terminal
- confirm `/health` succeeds
- confirm startup logs are readable
- confirm the packaged backend can import all runtime dependencies

Suggested commit:

- `build(backend): add sidecar packaging spike`

## Phase 1: Make Backend Configuration Relocatable

Tasks:

- remove packaged-mode dependence on repository-relative defaults
- add runtime config support for host, port, db path, raw data path, outputs
  path, and log path
- ensure startup creates missing directories automatically
- update CORS and any origin checks needed for the desktop runtime
- document the backend env contract expected from Tauri

Deliverable:

- a backend that can run entirely from Tauri-provided paths

Validation:

- start the backend from a temporary directory with only env-provided paths
- verify database creation
- verify raw and outputs directories are created correctly
- run backend smoke requests for assets, jobs, outputs, conversion configs, and
  conversions

Suggested commit:

- `refactor(backend): make settings desktop-relocatable`

## Phase 2: Add Tauri Sidecar Launch And Supervision

Tasks:

- add the Tauri shell plugin and sidecar permissions
- register the backend executable as an allowed external binary
- create Rust-side state for backend process metadata
- pick an available loopback port at startup
- spawn the backend sidecar with the required env vars
- stream or capture backend stdout and stderr for debugging
- shut down the child process when the app exits

Deliverable:

- Tauri can launch and stop the backend process automatically

Validation:

- run `tauri:dev` with sidecar mode enabled
- confirm the backend child starts without manual intervention
- confirm `/health` passes through the chosen dynamic port
- close the app and verify the backend child exits cleanly

Suggested commit:

- `feat(desktop): spawn backend sidecar from tauri`

## Phase 3: Add Runtime Backend Bootstrap To The Frontend

Tasks:

- expose a Tauri command or bootstrap channel that returns backend runtime
  details
- set `globalThis.__HEPHAES_BACKEND_BASE_URL__` from Tauri before the React app
  mounts
- keep `VITE_BACKEND_BASE_URL` as a development override
- add a startup-loading view while the app waits for backend readiness
- add a clear startup-failure view when the backend fails to come up

Deliverable:

- the packaged frontend uses the Tauri-provided backend URL automatically

Validation:

- confirm the frontend boots against a dynamic backend port
- confirm API and WebSocket URLs resolve from the same runtime base URL
- simulate backend startup failure and verify the failure UI appears

Suggested commit:

- `feat(frontend): bootstrap backend url from tauri runtime`

## Phase 4: Replace Desktop-Only Backend Dialog Flows

Tasks:

- add the Tauri dialog plugin
- move file and directory selection into the frontend desktop shell
- keep using existing backend register and scan APIs after a path is chosen
- remove the packaged-app dependency on backend `tkinter` and AppleScript
  dialogs
- decide whether `/register-dialog` remains as a legacy dev-only endpoint or is
  removed entirely

Deliverable:

- desktop file picking works through Tauri-native dialogs

Validation:

- verify single-file registration from the packaged app
- verify directory scan flows from the packaged app
- verify cancel flows do not create phantom jobs or partial state

Suggested commit:

- `feat(desktop): move asset selection to tauri dialogs`

## Phase 5: Bundle The Sidecar Into Desktop Builds

Tasks:

- add a build script that produces the backend sidecar artifact for the target
  platform
- place the built binary where Tauri expects external sidecars
- update Tauri config so the backend is included in dev and packaged builds
- ensure backend logs and crash artifacts are written into app-managed
  directories
- document the full build path for local packaging and CI

Deliverable:

- `tauri build` produces a desktop bundle that includes the backend sidecar

Validation:

- run a clean packaged build
- install or open the resulting bundle
- verify the app launches without the repo or a separately running backend

Suggested commit:

- `build(desktop): bundle packaged backend with tauri`

## Phase 6: Harden Startup, Shutdown, And Recovery

Tasks:

- add startup timeout handling with a user-visible error state
- add better logging around sidecar spawn failures and health-check failures
- ensure repeated app launches do not corrupt or lock the database unexpectedly
- ensure shutdown does not leave orphan backend processes behind
- verify upgrades preserve existing local app data

Deliverable:

- sidecar lifecycle is stable enough for normal desktop use

Validation:

- kill the backend during runtime and verify the app reports the failure
- test repeated open and close cycles
- test first-run and returning-user launch paths
- inspect logs for actionable failure details

Suggested commit:

- `fix(desktop): harden backend sidecar lifecycle`

## Phase 7: Full Parity And Release Validation

Tasks:

- run the existing frontend quality checks
- run packaged-app smoke tests across major routes
- verify at least one real mutation flow for inventory tagging
- verify at least one directory scan flow
- verify convert create and use flows
- verify outputs browsing and output detail flows
- verify replay and WebSocket behavior in the packaged app
- update docs for local development, packaging, and debugging

Deliverable:

- a sidecar-backed desktop app that is functionally usable end to end

Validation:

- `npm run lint`
- `npm run test`
- `npm run typecheck`
- `npm run build`
- `cargo check --manifest-path frontend/src-tauri/Cargo.toml`
- `npm run tauri:dev`
- `npm run tauri:build`
- packaged manual smoke pass covering dashboard, inventory, jobs, outputs,
  convert, and replay

Suggested commit:

- `test(desktop): validate packaged sidecar parity`

## Recommended Execution Order

1. prove backend packaging first
2. make backend settings portable
3. wire Tauri sidecar lifecycle
4. hand the runtime backend URL to the frontend
5. replace desktop-native dialog gaps
6. bundle the sidecar into release builds
7. harden failure handling and complete parity validation

## Tracking Rules During Implementation

- treat each phase as a separate milestone and separate commit
- do not start the next phase until the current phase has passing validation
- keep a short running checklist of failures found during packaged-app testing
- prefer small compatibility shims over backend or frontend rewrites

## Definition Of Done

The sidecar work is complete when:

- the packaged desktop app launches a working backend automatically
- no manual backend startup is required for normal usage
- backend storage is fully app-local
- frontend API and WebSocket traffic work against the runtime-provided backend
  URL
- desktop file picking no longer depends on backend-native GUI code
- packaged smoke tests pass across inventory, jobs, outputs, convert, and
  replay flows
