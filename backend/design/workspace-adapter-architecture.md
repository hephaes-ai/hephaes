# Backend Workspace Adapter Architecture

## Decision

The backend becomes a thin adapter over the `hephaes` package.

It should not own the durable local domain model. Instead, it should translate HTTP requests into `Workspace` operations and keep only the backend-specific concerns that do not belong in the package.

## Scope

### Owned by `backend/`

- FastAPI route handlers
- request validation and response shaping
- API-specific Pydantic schemas
- HTTP error mapping
- upload and dialog endpoints if they remain part of the backend UX
- background execution runner
- visualization preparation
- replay and streaming behavior

### Not owned by `backend/`

- workspace persistence
- asset catalog and indexing state
- tags
- saved configs, revisions, and draft revisions
- jobs
- conversion runs
- output artifact catalog
- dashboard aggregations based on durable local state

## Target Shape

```text
FastAPI routes
  -> validate request / shape response
  -> workspace-backed service adapters or mapper helpers
  -> hephaes.Workspace

Visualization / replay services
  -> read assets, metadata, jobs, and runs through Workspace
  -> own only visualization/replay-specific logic and cache files
```

## Route and Service Boundary

The backend should keep:

- route modules under `backend/app/api/`
- response mappers that translate workspace models into API payloads
- visualization and replay services
- background execution runner

The backend should stop owning:

- a separate SQLite database
- SQLAlchemy models for local durable state
- duplicate service logic for assets, configs, conversions, jobs, outputs, and dashboard queries

## Data Access Direction

All durable local state should flow through `Workspace`.

That means backend code should:

- resolve a workspace instance from app state
- call workspace methods
- translate package exceptions into HTTP responses
- translate package models into API response schemas

The backend should not:

- create or manage `app.db`
- write duplicate durable records outside the workspace
- couple route behavior to ORM models

## Visualization and Replay

Visualization and replay remain backend-owned.

They should:

- resolve assets and jobs through `Workspace`
- read imported asset files from the workspace
- keep visualization-specific cache files outside the package boundary
- keep websocket and streaming behavior backend-specific

## Benefits

- one source of truth for durable local state
- thinner backend code
- fewer migrations and less schema duplication
- cleaner adapter boundary for future UI layers

## Main Risks

### Risk: response-shaping code is still ORM-shaped

Mitigation:
Introduce explicit mapper helpers from workspace models to API payloads.

### Risk: visualization and replay still assume backend-owned state

Mitigation:
Repoint those services to workspace lookups early, while keeping their transport-specific logic local to the backend.

### Risk: backend keeps too much duplicate business logic

Mitigation:
Treat service modules as adapters and delete duplicate durable-state behavior once the workspace equivalent exists.
