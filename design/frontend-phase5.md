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
