# Frontend Phase 8C

## Goal

Embed the official Rerun viewer using backend-provided viewer sources and complete visualization preparation and failure-handling workflows.

## Depends On

- [frontend-phase8a.md](frontend-phase8a.md)
- [frontend-phase8b.md](frontend-phase8b.md)
- [backend-phase9.md](backend-phase9.md)
- [backend-phase8.md](backend-phase8.md)

## Current State (Already Implemented)

The current frontend codebase already includes:

- visualization route, episode selection, and return-navigation flow
- timeline and samples integration with synchronized cursor playback
- transport controls and speed controls
- lane visibility toggles with URL persistence
- per-lane payload disclosure in scrubber rows (replacing the prior standalone inspector panel)
- viewer-source status card with loading/error/missing handling (placeholder viewer, no official embed yet)
- timeline timestamp contract alignment (`start_timestamp_ns` / `end_timestamp_ns`) and cursor-synced payload fetch behavior

These are phase 8A/8B outcomes and should not be re-scoped into 8C implementation tasks.

## Scope

Phase 8C should implement only:

- reusable official Rerun viewer wrapper component
- prepare-visualization trigger and job handoff flow
- viewer source readiness polling and live transition
- explicit viewer integration states and recovery paths
- final visualization-specific UX polish around embedded viewer states

## Tasks

### Viewer source and prepare APIs

- Extend [frontend/lib/api.ts](../frontend/lib/api.ts) with typed support for:
  - POST /assets/{asset_id}/episodes/{episode_id}/prepare-visualization
- Reuse existing GET /jobs/{job_id} API and job status surfaces already present in jobs pages.
- Add/extend hooks in [frontend/hooks/use-backend.ts](../frontend/hooks/use-backend.ts) to trigger preparation and revalidate viewer-source/job state.

### Rerun wrapper component

- Add reusable viewer wrapper component under [frontend/components](../frontend/components) for official Rerun embedding.
- Accept backend-provided viewer source manifest or URL as primary input.
- Keep integration seam clear between page state and embedded viewer props/events.

### Integration states

- Implement explicit states in viewer wrapper and page shell:
  - loading source
  - preparation in progress
  - missing source
  - viewer/source version mismatch
  - backend error
- Provide actionable messages and retry controls where appropriate.

### Preparation workflow

- Add Prepare visualization action when source is unavailable.
- On prepare request:
  - trigger backend preparation
  - display linked job state (job id, status, and navigation to jobs/job detail)
  - poll until source readiness or failure
- Transition automatically from preparation state into live viewer when source becomes available.

### Polish and resilience

- Ensure viewer container remains legible in light and dark modes.
- Validate unsupported-data handling without crashing page controls.
- Verify viewer load failures do not break transport/scrubber shell or lane payload disclosure.

## Deliverable

By the end of phase 8C, users can prepare visualization data when needed, load the official Rerun viewer from backend-provided sources, and recover clearly from unsupported or failed states while retaining synchronized scrubber/payload behavior from 8B.

## Verification

- verify prepare-visualization flow with job handoff
- verify automatic transition to live viewer when source is ready
- verify missing-source, mismatch, and backend-error states
- verify lane payload dropdowns remain functional while viewer states transition
- run:
  - npm run lint
  - npm run typecheck
  - npm run build
