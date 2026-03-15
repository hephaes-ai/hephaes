# Frontend Phase 1

## Goal

Build the first usable local frontend slice on top of the Phase 1 backend so the product has a real end-to-end loop:

- connect to the local backend
- register local assets
- view the inventory
- open an asset detail view

This phase should optimize for feedback and fast iteration, not polish.

This phase should fully consume the Backend Phase 1 functionality that already exists. It is not a placeholder frontend phase. Its purpose is to validate the real backend implementation through a usable UI.

## Depends On

- [backend-phase1.md](/Users/danielyoo/workspace/hephaes/design/backend-phase1.md)

## Product Scope

Implement the smallest useful frontend shell with:

- app bootstrap in `frontend/`
- a top-level app layout
- backend connectivity check
- an inventory page
- a registration form
- an asset detail page
- basic empty, loading, and error states

Phase 1 should use file-path registration because that is what the backend currently supports.

The frontend in this phase should be able to exercise every user-facing capability from Backend Phase 1:

- confirm backend connectivity
- register a file by path
- load the asset inventory
- open an individual asset detail view
- surface backend validation errors to the user

## Recommended UI Surfaces

### App shell

- top navigation or app header
- primary route outlet
- lightweight global feedback area for success and error messages

### Inventory page

- file registration form
- asset list or table
- columns for:
  - file name
  - file type
  - file size
  - indexing status
  - registration date
  - last indexed time
- empty state when no assets exist
- inline or nearby success and error feedback for registration attempts

### Asset detail page

- base asset information
- indexing status
- last indexed time
- placeholder sections for metadata, tags, and conversions

The detail page does not need advanced actions yet, but it should faithfully display what the Backend Phase 1 detail endpoint returns.

## State and Data Guidance

Recommended architecture for this phase:

- route-driven screens for inventory and asset detail
- one API client module for backend calls
- one data-fetching layer for caching and refetching
- local component state for form inputs and transient UI state

Even if search and filters are not implemented yet, design the inventory page so URL-based state can be added later without a rewrite.

Do not fake backend responses in normal app usage for this phase. The goal is to test the real Phase 1 backend through the frontend.

## Backend Endpoints Used

- `GET /health`
- `POST /assets/register`
- `GET /assets`
- `GET /assets/{asset_id}`

## Deliverable

By the end of phase 1, a user should be able to:

- open the local app
- confirm the backend is reachable
- register a `.bag` or `.mcap` file by path
- see that asset appear in the inventory
- open the asset detail view
- observe backend-driven validation errors such as duplicate registration or invalid paths
- use the UI as a real verification surface for all Backend Phase 1 routes

## Notes

This phase is the frontend counterpart to the current backend MVP. It is primarily about validating API shape, navigation flow, and the inventory/detail model before adding heavier workflows.

If the frontend uncovers awkward API response shapes, missing fields, or rough UX edges in the current backend, those should be treated as valid feedback for tightening Backend Phase 1 before moving on.

## Tasks

### Project setup

- Create the initial `frontend/` application structure.
- Choose and set up the frontend stack for the local app.
- Add the minimal tooling needed to run the frontend locally against the backend.
- Decide how the frontend will read the backend base URL in development.

### App bootstrap

- Create the root app shell with a header or navigation area.
- Add top-level routing for at least:
  - inventory page
  - asset detail page
- Add a lightweight global feedback mechanism for success and error messages.
- Add a backend connectivity check that uses `GET /health`.

### API integration

- Create a small API client module for backend requests.
- Add typed helpers for:
  - `GET /health`
  - `POST /assets/register`
  - `GET /assets`
  - `GET /assets/{asset_id}`
- Normalize backend error handling so UI components can show consistent messages.

### Inventory page

- Build the inventory page layout.
- Add a registration form for local file-path submission.
- Validate that the form cannot submit an empty path.
- Submit the form to `POST /assets/register`.
- Refresh or invalidate the asset list after a successful registration.
- Show success feedback for successful registrations.
- Show backend-driven error feedback for invalid paths or duplicates.
- Render the asset inventory from `GET /assets`.
- Display the required columns:
  - file name
  - file type
  - file size
  - indexing status
  - registration date
  - last indexed time
- Add an empty state for when no assets are registered yet.
- Make each asset row navigable to its detail view.

### Asset detail page

- Add route handling for an individual asset detail view.
- Fetch asset data from `GET /assets/{asset_id}`.
- Display the base asset information returned by the backend.
- Display indexing status and last indexed time.
- Add placeholder sections for metadata, tags, and conversions so the layout can grow in later phases.
- Add loading and not-found states for the detail page.

### State and navigation

- Keep inventory data fetching separate from view components.
- Structure the inventory page so URL-based search and filter state can be added later.
- Ensure navigation from inventory to detail and back feels stable.
- Preserve enough inventory state that the user can return without losing the basic list context.

### Local verification

- Run the frontend and backend together locally.
- Confirm the frontend shows backend connectivity status from the real backend.
- Register a real `.bag` or `.mcap` file path through the UI.
- Confirm the new asset appears in the inventory without manual refresh.
- Open the asset detail page and confirm it matches backend data.
- Try duplicate registration and invalid path submission to verify user-visible error handling.

### Nice-to-have cleanup

- Add a short `frontend/README.md` with local install and run instructions.
- Add a brief note on how the frontend should be started alongside the backend during development.
- Document any assumptions about the backend base URL or proxy configuration.
