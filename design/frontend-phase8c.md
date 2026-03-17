# Frontend Phase 8C

## Goal

Embed the official Rerun viewer using backend-provided viewer sources and complete visualization preparation and failure-handling workflows.

## Depends On

- [frontend-phase8a.md](frontend-phase8a.md)
- [frontend-phase8b.md](frontend-phase8b.md)
- [backend-phase9.md](backend-phase9.md)
- [backend-phase8.md](backend-phase8.md)

## Scope

Implement:

- reusable official Rerun viewer wrapper component
- prepare-visualization trigger and job handoff flow
- viewer source readiness polling and live transition
- explicit viewer integration states and recovery paths
- final cross-surface UX polish for visualization

## Tasks

### Viewer source and prepare APIs

- Extend [frontend/lib/api.ts](../frontend/lib/api.ts) with typed support for:
  - POST /assets/{asset_id}/episodes/{episode_id}/prepare-visualization
  - GET /jobs/{job_id} reuse through existing jobs APIs
- Reuse existing workflow status utilities and badges for prep status display.

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
  - display linked job state
  - poll until source readiness or failure
- Transition automatically from preparation state into live viewer when source becomes available.

### Cross-surface coherence

- Keep navigation continuity between:
  - inventory
  - asset detail
  - jobs and job detail
  - visualization route
- Reuse existing request feedback and status patterns from prior frontend phases.
- Keep success states quiet and failures explicit.

### Polish and resilience

- Ensure viewer container remains legible in light and dark modes.
- Validate unsupported-data handling without crashing page controls.
- Verify viewer load failures do not break transport/scrubber shell.

## Deliverable

By the end of phase 8C, users can prepare visualization data when needed, load the official Rerun viewer from backend-provided sources, and recover clearly from unsupported or failed states.

## Verification

- verify prepare-visualization flow with job handoff
- verify automatic transition to live viewer when source is ready
- verify missing-source, mismatch, and backend-error states
- verify navigation continuity to and from jobs/inventory/detail routes
- run:
  - npm run lint
  - npm run typecheck
  - npm run build
