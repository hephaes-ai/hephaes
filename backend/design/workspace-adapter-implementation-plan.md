# Backend Workspace Adapter Implementation Plan

## Outcome

Make the backend a thin HTTP and visualization/replay adapter over `hephaes.Workspace`.

After this work, the backend should no longer own a separate durable SQLite database for local application state.

## Guiding Rules

- Resolve all durable local state through `Workspace`.
- Keep backend-specific code focused on HTTP, visualization, replay, and execution orchestration.
- Preserve existing API responses until frontend changes are intentional.
- Delete SQLAlchemy persistence only after the backend is fully workspace-backed.

## Phase 1: Add Workspace App Dependency

### Goals

- Give the backend a first-class workspace dependency.

### Tasks

- Add backend configuration for workspace root discovery.
- Initialize or open a workspace during app startup.
- Store the workspace instance on app state.
- Add a backend dependency such as `get_workspace`.
- Stop treating `app.db` as the backend's long-term source of truth.

### Exit Criteria

- Routes and services can resolve a workspace instance from app state.

## Phase 2: Add Mapper Helpers

### Goals

- Break response building away from ORM assumptions.

### Tasks

- Add mapper helpers from workspace models to API response payloads.
- Update route builders to use explicit mappers instead of `from_attributes` assumptions where needed.
- Audit tests that currently depend on ORM models directly.

### Exit Criteria

- API response shaping no longer depends on SQLAlchemy model instances.

## Phase 3: Migrate Durable-State Routes

### Goals

- Repoint the main backend route groups to `Workspace`.

### Tasks

- Migrate assets, indexing, and tags routes.
- Migrate saved config and draft-persistence routes.
- Migrate jobs, conversion runs, outputs, and dashboard routes.
- Delete duplicate service logic as each slice moves over.

### Exit Criteria

- Durable-state routes read and write through `Workspace` only.

## Phase 4: Repoint Visualization and Replay Readers

### Goals

- Keep visualization and replay backend-owned, but make them read workspace-owned state.

### Tasks

- Replace asset lookups in replay and visualization services with workspace lookups.
- Replace job and run lookups with workspace-backed data access.
- Keep visualization cache generation and replay transport logic in the backend.

### Exit Criteria

- Visualization and replay depend on workspace state, not ORM tables.

## Phase 5: Remove SQLAlchemy Persistence

### Goals

- Delete the duplicate backend durability layer.

### Tasks

- Remove backend DB initialization and session wiring that are no longer used.
- Remove SQLAlchemy models for duplicated local state.
- Delete or simplify services that existed only to manage duplicate persistence.
- Update tests and docs to match the workspace-backed backend.

### Exit Criteria

- The backend no longer owns a separate durable SQLite database for local state.

## Validation Checklist

- backend route tests still pass with unchanged API responses
- visualization and replay tests still pass after workspace repointing
- manual API smoke checks work against a workspace-backed app

## Main Risks

### Response contract drift

Mitigation:
Keep mapper helpers explicit and preserve current response shapes during migration.

### Hidden ORM coupling

Mitigation:
Audit route helpers and tests early, especially where they currently instantiate or query ORM models directly.

### Adapter logic grows back into business logic

Mitigation:
Keep the backend implementation focused on translation, orchestration, visualization, and replay.
