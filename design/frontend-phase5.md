# Frontend Phase 5

## Goal

Expose conversion as a complete user workflow from asset selection through submission.

## Depends On

- [backend-phase5.md](/Users/danielyoo/workspace/hephaes/design/backend-phase5.md)
- [backend-phase6.md](/Users/danielyoo/workspace/hephaes/design/backend-phase6.md)
- [frontend-ui-guidelines.md](/Users/danielyoo/workspace/hephaes/design/frontend-ui-guidelines.md)

## Product Scope

Implement:

- conversion entry from selected assets
- format selection for Parquet and TFRecord
- conversion configuration inputs supported by the backend
- a review step or summary panel
- submission feedback
- initial job-status handoff after submission

The conversion flow should use shadcn dialogs, sheets, forms, and summary cards where possible, while keeping the review UI simple and uncluttered.

## Recommended UI Surfaces

### Convert modal or page

- selected-assets summary
- output format selector
- config fields
- validation and submit controls
- final confirmation summary

### Inventory and detail integration

- convert action in the bulk toolbar
- convert action on the detail page

## State and Data Guidance

Recommended behavior:

- prevent duplicate conversion submissions while a request is pending
- preserve current inventory selection while the conversion flow is open
- treat conversion settings as structured state, not loose form fields, so they can grow later

## Backend Endpoints Used

- `POST /conversions`
- `GET /conversions`
- `GET /conversions/{conversion_id}`

## Deliverable

By the end of phase 5, a user should be able to:

- select one or more assets
- choose Parquet or TFRecord
- configure and review a conversion
- submit a conversion request to the backend
- see initial conversion status after submission

## Tasks

### API integration

- Extend the frontend API layer in [frontend/lib/api.ts](/Users/danielyoo/workspace/hephaes/frontend/lib/api.ts) to support:
  - `POST /conversions`
  - `GET /conversions`
  - `GET /conversions/{conversion_id}`
- Add typed request and response models for:
  - conversion creation payloads
  - conversion summaries
  - conversion detail responses
  - linked job summaries if the backend returns them inline
- Add SWR helpers or equivalent cache wiring so conversion creation and status fetches fit the existing frontend data patterns.
- Keep the conversion payload structure aligned with backend phase 6 rather than inventing frontend-only field names.

### Conversion state model

- Introduce structured conversion form state instead of loose individual inputs.
- Model at least:
  - selected asset IDs
  - output format
  - output-specific config
  - optional resample settings if phase 5 exposes them
  - optional custom mapping input if the backend supports it in the first cut
  - submission and validation state
- Keep the state shape ready for future expansion so adding more conversion knobs later does not require a full refactor.
- Prevent duplicate submits while a conversion request is already in flight.

### Shared conversion UI

- Add minimal shadcn-first conversion UI primitives such as:
  - dialog or sheet shell
  - format selector
  - config field groups
  - summary cards
  - status callouts
- Keep the conversion surface visually quiet and focused, with the selected assets and format choice as the primary anchors.
- Prefer compact forms and summaries over large wizard-like layouts unless the complexity truly requires it.
- Reuse existing feedback and card patterns so the conversion flow feels native to the rest of the app.

### Inventory integration

- Add a convert action to the inventory bulk toolbar for the current selection.
- Disable or hide conversion entry when nothing is selected.
- Make the selected-asset count and scope obvious before the user submits a conversion.
- Preserve current inventory selection while the conversion surface is open.
- Decide whether conversion entry should be available only for indexed assets or whether the UI should surface inline validation when unindexed assets are included.

### Asset detail integration

- Add a convert action on the asset detail page for single-asset conversion.
- Prepopulate the conversion surface with the current asset when launched from detail view.
- Keep the detail-page action placement consistent with the existing indexing and tag actions.
- Ensure users can return to the detail page context without losing track of the asset they were viewing.

### Configuration form

- Add format selection for:
  - Parquet
  - TFRecord
- Show only the configuration inputs relevant to the selected format.
- Add any backend-supported shared settings such as:
  - resampling method
  - resampling frequency
  - write-manifest toggle
- Decide whether custom mapping is exposed in phase 5 as:
  - a raw JSON editor
  - a simple topic-to-field form
  - or a deferred follow-up if the UX would be too rough
- Keep validation immediate and readable so users understand what will be sent before submission.

### Review and submission UX

- Add a review step or summary panel that clearly shows:
  - selected assets
  - chosen output format
  - key conversion options
  - any notable validation warnings
- Make submit and cancel actions easy to scan and hard to misclick.
- Keep normal success handling lightweight while still giving the user a clear handoff to the created conversion or linked job.
- Decide whether submission should close the modal immediately on success or remain open long enough to show the created conversion summary.

### Initial status handoff

- After submission, surface the created conversion status without making the user guess what happened.
- Show at least:
  - conversion ID
  - linked job state if available
  - current status
  - output path or next-step information when the backend returns it
- Decide whether the first-cut handoff is:
  - an inline success panel
  - a redirect to a conversion detail view
  - or a lightweight toast plus link
- Keep the handoff simple, since a fuller conversion history UI can evolve in later work.

### Error and feedback UX

- Show inline validation for malformed config before the request is sent when possible.
- Surface backend conversion validation failures clearly, especially for:
  - unindexed assets
  - invalid mapping payloads
  - unsupported config combinations
- Surface execution failures without losing the user’s submitted config state.
- Keep ordinary success paths quiet and concise so the conversion flow stays clean.
- Reuse the existing app feedback provider rather than adding a second notification pattern.

### Local verification

- Run the frontend against a real local backend with phase 6 conversion support enabled.
- Confirm conversion entry works from the inventory selection flow.
- Confirm conversion entry works from the asset detail page.
- Confirm Parquet and TFRecord submissions send the expected payloads.
- Confirm the review or summary step reflects the final submitted configuration accurately.
- Confirm the UI handles backend validation errors and failed conversions clearly.
- Confirm the initial status handoff after submission gives the user enough information to trust that the conversion was created.
