# Conversion Authoring And Reusable Configs

## Purpose

This document tracks frontend changes that will be needed to support the new converter authoring model.

This is a planning note only. It does not imply that frontend implementation should start yet.

The target UX is:

- inspect an asset before conversion
- draft a conversion spec visually
- preview the draft before running it
- save reusable configs
- reopen and edit saved configs later
- execute conversions from either a draft or a saved config

The frontend should stay thin and call backend-owned authoring APIs instead of implementing converter logic locally.

## Ownership Boundary

### `hephaes` should own

- inspection, inference, draft, preview, validation, and migration logic

### Backend should own

- stable API contracts
- reusable-config persistence
- capability metadata
- conversion execution orchestration

### Frontend should own

- editing UX
- review and preview presentation
- saved-config management UI
- routing and page flow
- import and export affordances

The frontend should not hard-code converter enums, inference rules, or migration rules in TypeScript.

## Why The Current Conversion Route Is Not Enough

The current `/convert` work is still shaped around immediate submission.

That is not enough for the future authoring workflow because the UI will also need:

- inspection before submission
- capability-driven forms
- reusable config selection
- saved draft and revision flows
- preview before execution
- migration messaging when older configs are reopened

## Frontend Capabilities To Track

### 1. Capability-Driven Form Rendering

The frontend will need a capability payload from the backend that describes:

- supported row strategies
- supported feature source kinds
- supported transform kinds
- supported dtypes
- current spec version
- preview defaults and limits

This should drive editor controls instead of hard-coded frontend lists.

### 2. Inspection Flow

The UI will need a way to:

- select assets or sources to inspect
- view topics and message types
- drill into field candidates
- understand likely shapes and warnings

This likely becomes an early step in the conversion page rather than a separate hidden utility.

### 3. Draft-Spec Editing Flow

The UI will need to support:

- generating a draft from inspection
- editing row strategy
- selecting feature candidates
- editing transforms and output settings
- seeing assumptions and warnings from inference

### 4. Preview Flow

The UI will need to show:

- sample assembled rows
- feature summaries
- presence and missing-data behavior
- unresolved warnings

Preview should feel like a review step, not like a failed conversion screen.

### 5. Reusable Config Management

The UI will need to support:

- list saved configs
- create a saved config from a draft
- duplicate a config
- rename and describe a config
- reopen a saved config into the editor
- execute from a saved config

## Route And Page Work To Track

The existing conversion-page plan is still useful, but the route will eventually need to support more than a simple submit form.

Future route states likely include:

- asset selection context
- inspection state
- draft editing state
- preview state
- saved-config selection state
- post-submit status state

Likely main surface:

- `frontend/app/convert/`

Potential supporting surfaces:

- saved-config picker
- draft warning panel
- preview panel
- feature editor sections

## State Management Changes To Track

The frontend will likely need clearer separation between:

- local UI state
- backend resource state
- draft editor state
- post-submit execution state

Important rule:

- semantic validation should come from backend and `hephaes`
- frontend validation should stay focused on UX issues such as incomplete required fields or malformed local inputs

## API Client Changes To Track

Likely additions to `frontend/lib/api.ts`:

- fetch conversion capabilities
- run topic inspection
- run field inspection
- generate draft spec
- preview draft spec
- list saved configs
- create saved config
- update saved config
- duplicate saved config

The frontend should consume typed responses from the backend rather than reconstructing contracts ad hoc in components.

## UI Components To Track

Potential component areas:

- conversion capability loader
- inspection step
- field candidate browser
- draft feature editor
- transform editor
- preview panel
- saved-config picker
- saved-config metadata editor
- migration warning banner

These do not all need to be separate files, but the work should be planned as if the route becomes a full authoring surface.

## File Areas Likely To Change Later

- `frontend/lib/api.ts`
- `frontend/lib/types.ts`
- `frontend/hooks/`
- `frontend/app/convert/page.tsx`
- `frontend/app/convert/conversion-page.tsx`
- `frontend/app/convert/conversion-workflow.tsx`
- `frontend/components/conversion-dialog.tsx`
- `frontend/components/`
- `frontend/design/conversion-page-route.md`
- `frontend/design/jobs-and-conversions.md`

## Phased Task List

### Phase 1: Contract consumption

- [ ] Add typed client helpers for backend authoring APIs.
- [ ] Add capability-loading helpers so forms can render from backend-owned metadata.
- [ ] Refactor any local conversion payload helpers so they can work with richer spec payloads.

### Phase 2: Inspection and draft UX

- [ ] Add inspection UI for topics and field candidates.
- [ ] Add draft generation flow from inspection results.
- [ ] Add editing UI for draft specs and warnings.

### Phase 3: Preview UX

- [ ] Add preview panels for assembled rows and extracted features.
- [ ] Add clear warning and error presentation before execution.
- [ ] Separate preview from final conversion submission.

### Phase 4: Reusable config UX

- [ ] Add saved-config browsing and selection.
- [ ] Add create, rename, duplicate, and update flows.
- [ ] Add execute-from-saved-config flow.

### Phase 5: Migration and polish

- [ ] Show migration notices for older saved configs.
- [ ] Add import and export affordances if the product needs them.
- [ ] Make the conversion page resilient to refresh and deep-linking for saved config and status views.

## Risks

- Hard-coding transform options or dtype rules in the frontend will drift from `hephaes`.
- Mixing draft editing and post-submit status too tightly will make the route hard to reason about.
- Large draft specs can become unwieldy without a strong editing layout and progressive disclosure.
- Saved-config UX will feel brittle unless migration states are communicated clearly.

## Acceptance Criteria

- The frontend can render authoring controls from backend-owned capability metadata.
- Users can inspect, draft, preview, save, reopen, and execute conversion configs without writing Python code.
- The conversion route can support reusable configs and previews without duplicating converter business logic in React.
