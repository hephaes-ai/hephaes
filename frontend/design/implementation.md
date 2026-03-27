# Frontend Tauri Implementation Plan

## Goal

Convert `frontend/` from Next.js to a Tauri desktop app in small steps while
continuing to use the existing FastAPI backend as an external dependency.

## Guiding Constraints

- keep the backend running separately during this phase
- preserve current UX and API behavior as much as possible
- avoid mixing backend sidecar work into this migration
- keep the app shippable at intermediate checkpoints

## Phase 0: Baseline And Guardrails

- confirm the current frontend route and feature inventory
- record a short parity checklist:
  - dashboard loads
  - inventory list/filter/tag flows work
  - asset detail loads
  - jobs list/detail loads
  - outputs list/detail loads
  - convert create/use flows work
  - replay page connects to WebSocket and loads the viewer
- keep the backend start command unchanged for now

## Phase 1: Add Tauri And Vite Scaffolding

- add Tauri to `frontend/`
- add `frontend/src-tauri`
- add Vite entry files:
  - `frontend/index.html`
  - `frontend/src/main.tsx`
  - `frontend/src/App.tsx`
  - `frontend/vite.config.ts`
- update `package.json` scripts for:
  - `dev`
  - `build`
  - `tauri:dev`
  - `tauri:build`
- keep the current Next files in place until route parity is reached

Deliverable:

- a blank or skeletal Tauri desktop shell that can render a React app

## Phase 2: Move Shared Code Out Of Next App Structure

- move reusable code from the current tree into `frontend/src`
- keep import paths stable where possible

Recommended target grouping:

- `frontend/components` -> `frontend/src/components`
- `frontend/hooks` -> `frontend/src/hooks`
- `frontend/lib` -> `frontend/src/lib`
- `frontend/app/globals.css` -> `frontend/src/app/globals.css` or
  `frontend/src/styles/globals.css`

Notes:

- route wrapper files do not need to be preserved
- feature page components can be moved mostly intact
- `public/` assets can stay where they are

## Phase 3: Replace Next-Specific APIs

Replace framework-specific dependencies before moving routes:

- `next/link` -> `react-router-dom` `Link`
- `next/navigation`:
  - `useRouter` -> `useNavigate`
  - `usePathname` -> `useLocation`
  - `useSearchParams` -> React Router search param hooks
  - server `redirect(...)` -> client redirects
- `next/image` -> normal `img`
- `next/font/google` -> local font import or plain CSS font stack

This phase should leave shared UI components framework-neutral.

## Phase 4: Rebuild Routing With React Router

Create explicit client routes and map existing pages into them.

Suggested route ownership:

- `dashboard` from `app/dashboard/dashboard-page.tsx`
- `inventory` from `app/inventory/inventory-page.tsx`
- `asset detail` from `app/assets/[assetId]/asset-detail-page.tsx`
- `jobs` from `app/jobs/jobs-page.tsx`
- `job detail` from `app/jobs/[jobId]/job-detail-page.tsx`
- `outputs` from `app/outputs/outputs-page.tsx`
- `output detail` from `app/outputs/[outputId]/output-detail-page.tsx`
- `replay` from `app/replay/visualization-page.tsx`
- `convert create/use` from `app/convert/conversion-authoring-workspace.tsx`

Special handling:

- root `/` becomes a simple client redirect
- `/visualize` becomes a simple client redirect to `/replay`
- `/convert` becomes a client bootstrap route

For `/convert`, reimplement the current logic as:

- read search params client-side
- call the existing backend endpoint for saved configs
- navigate to `/convert/use` if saved configs exist
- otherwise navigate to `/convert/new`

## Phase 5: Backend Config And Connectivity

- replace Next env usage with Vite env usage
- centralize backend base URL resolution in `src/lib/api.ts`
- keep default backend URL as `http://127.0.0.1:8000`
- keep WebSocket URL derivation from the same base URL
- surface a clearer backend-unavailable state in the desktop shell

Good enough for phase 1:

- build-time config with `VITE_BACKEND_BASE_URL`

Better follow-up:

- a tiny runtime config layer so the desktop app can swap backend addresses
  without rebuilding

## Phase 6: Tauri Shell Integration

Keep Tauri integration minimal at first.

Current status:

- completed by the scaffold and shell-validation work already landed in phases
  1 through 5
- revalidated with `desktop:build`, `cargo check`, and `tauri:dev` after the
  routing and backend-config migrations

Needed immediately:

- app window configuration
- app name and icons
- dev/build packaging

Nice to defer:

- native dialogs
- opener integration
- updater
- notifications
- backend process management

## Phase 7: Testing And Parity Pass

Run frontend checks after each major slice:

- lint
- typecheck
- unit tests
- Vite production build
- Tauri dev launch

Manual smoke test:

1. start FastAPI separately
2. launch `tauri:dev`
3. verify each major route
4. verify at least one mutation flow:
   - tagging
   - scan directory
   - create conversion
5. verify replay WebSocket connects and viewer loads

## Recommended Execution Order

1. scaffold Vite + Tauri
2. move shared code
3. replace Next-only imports
4. wire React Router
5. migrate simple routes:
   - dashboard
   - inventory
   - jobs
   - outputs
6. migrate detail routes
7. migrate convert flow
8. verify replay and viewer last
9. remove obsolete Next files and dependencies

## Cleanup At The End

- delete `frontend/app` route wrappers that are no longer needed
- remove Next.js from `package.json`
- remove `next-env.d.ts`
- replace Next eslint config if it is still present
- update `frontend/README.md` with the new dev and build commands

## Definition Of Done

The migration is done when:

- `frontend/` builds with Vite instead of Next
- the app launches through Tauri
- all user-facing routes work against a separately running backend
- Next.js is no longer required to run the desktop frontend
- the repository is ready for a later backend sidecar phase without needing to
  redo the frontend shell work
