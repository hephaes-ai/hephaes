# Conversion Page Route

## Goal

Replace the current modal conversion experience with a dedicated page so conversion setup, submission, and live status all live on their own URL.

The page should keep the same backend behavior that exists today:

- validate the selected assets before submission
- create a conversion through the existing backend contract
- keep polling while the conversion or linked job is active
- surface links to the resulting job and outputs

The main change is navigation and layout, not workflow semantics.

## Current State

Today the conversion flow is centered in `components/conversion-dialog.tsx`.

That component currently owns:

- the conversion form state
- custom mapping validation
- payload construction
- submission through `useCreateConversion()`
- live polling after a conversion is created
- the post-submit status view

The dialog is launched from:

- `components/inventory-page.tsx` for selected assets
- `components/asset-detail-page.tsx` for the current asset

This works, but it has a few product drawbacks:

- the form feels cramped for a multi-section workflow
- the state is not naturally shareable or bookmarkable
- the page loses context if the browser refreshes while the dialog is open
- the dialog chrome makes the conversion flow feel secondary instead of intentional

## Proposed UX

Use a dedicated route for the conversion workflow:

```text
/convert?asset_ids=asset_a,asset_b
/convert?asset_ids=asset_a,asset_b&conversion_id=conv_123
```

Recommended query params:

- `asset_ids`: comma-separated selected asset IDs
- `conversion_id`: present after submission so the status view can rehydrate on refresh
- `from`: return href back to the source page

The page should support two states:

- draft state, before submission
- status state, after a conversion has been created

The status state should update the URL with the created `conversion_id` and keep the originating `asset_ids` so the page can be re-opened directly later without losing context.

## Route Choice

`/convert` is the right first route for this flow.

Why:

- it is an action page, not a browseable resource list
- it is short and easy to reach from inventory and asset detail
- it does not imply that a top-level conversions index already exists

I would not add a permanent shell tab for it in phase 1. The page is a launch surface, not a primary destination.

## Page Structure

The page should reuse the current form sections, but give them room to breathe.

Recommended structure:

- header with back link, title, and short guidance
- selected asset summary
- left/main column for form sections
- right column or sticky panel for review and live status
- footer actions for cancel, submit, open job, and view outputs

The existing section order can stay mostly intact:

- output format
- options
- mapping
- review

Once a conversion exists, the page should switch the main body into a status view instead of closing or redirecting away immediately.

## Data Model

The conversion page can stay lightweight if it reuses existing backend hooks.

Suggested data flow:

- resolve selected assets by reading `asset_ids` from the query string
- load the full asset summaries with `useAssets()`
- reuse `useCreateConversion()` for submission and cache revalidation
- use `useConversion(conversion_id)` when the page is in status mode

This avoids introducing a new backend endpoint just to support the page.

### Selected Assets

The page should treat missing or stale asset IDs as a blocking state.

If a URL contains `asset_ids` that no longer resolve, show an alert and do not allow submission until the selection is corrected.

### Submission State

The page should keep the same validation rules as the dialog:

- no submission when selected assets are unindexed
- no submission when the custom mapping JSON is invalid
- no submission when the resample frequency is invalid
- no submission while a request is already in flight

## Implementation Plan

### Phase 1: Extract Shared Conversion Logic

Pull the form and payload logic out of the dialog so the page can reuse it cleanly.

Recommended extraction targets:

- `createDefaultFormState()`
- `parseCustomMapping()`
- `buildConversionPayload()`
- the form state types

Likely home for shared helpers:

- `lib/navigation.ts` for a `buildConversionHref()` helper
- a small conversion helper module if the form logic starts to grow

Keep the backend mutation hook in place. `useCreateConversion()` already handles the revalidation work the page needs.

### Phase 2: Add the New Page

Create a new route entrypoint and a route component:

- `app/convert/page.tsx`
- `components/conversion-page.tsx`

The page component should:

- parse the query string
- resolve selected assets
- render the draft form or status view
- keep polling while the conversion or linked job is active
- update the URL with `conversion_id` after a successful submission

The page should also provide a clear back action using `resolveReturnHref()`.

### Phase 3: Switch Launch Points

Update the existing conversion buttons so they navigate instead of opening a dialog.

The launch points are:

- inventory bulk conversion for selected assets
- asset detail conversion for the current asset

Both should use the same route builder so the selection and return path stay consistent.

### Phase 4: Retire The Dialog Entry Points

Once the page is wired up, remove the local dialog state from the inventory and asset detail surfaces.

At that point:

- `ConversionDialog` should no longer be mounted by route pages
- the page should become the canonical conversion surface
- any remaining dialog wrapper can be deleted after the cutover is stable

## Implementation Tasks

Use this checklist to turn the plan into incremental PR-sized work.

### 1. Shared helpers and route contract

- [ ] Add a navigation helper in `frontend/lib/navigation.ts` for building `/convert` links from `asset_ids`, `conversion_id`, and `from`.
- [ ] Extract the conversion form-state types and payload helpers out of `frontend/components/conversion-dialog.tsx` so the page can reuse them cleanly.
- [ ] Keep `useCreateConversion()` as the mutation boundary so the page inherits the existing cache revalidation behavior.

### 2. New conversion page scaffold

- [ ] Add `frontend/app/convert/page.tsx` with the same Suspense pattern used by the other routes.
- [ ] Create `frontend/components/conversion-page.tsx` and a matching fallback skeleton.
- [ ] Parse `asset_ids`, `conversion_id`, and `from` from the query string.
- [ ] Resolve selected assets from `useAssets()` and show a blocking state when the selection is missing or stale.
- [ ] Reuse `resolveReturnHref()` to keep the back navigation local to the app.

### 3. Draft conversion flow

- [ ] Render the existing conversion sections on the page: output format, options, mapping, and review.
- [ ] Keep the same validation rules for indexed assets, custom mapping JSON, and resample frequency.
- [ ] Submit through `useCreateConversion()` and keep the created conversion in local state.
- [ ] Update the route to include the created `conversion_id` after a successful submit so the status view can survive refresh.
- [ ] Preserve a clear path back to the originating inventory or asset detail view.

### 4. Live status flow

- [ ] Load the created conversion with `useConversion(conversion_id)` when the page is in status mode.
- [ ] Poll every 1.5 seconds while the conversion or linked job is active.
- [ ] Surface conversion status, job status, output path, output files, and error state in the page view.
- [ ] Keep the links to job detail and outputs available after submission.
- [ ] Revalidate related caches after refreshes so the page stays in sync with the rest of the app.

### 5. Launch-point migration

- [ ] Update the inventory convert action to navigate to `/convert` instead of opening the dialog.
- [ ] Update the asset detail convert action to navigate to `/convert` instead of opening the dialog.
- [ ] Pass the selected asset IDs and source href through the URL so the conversion page can reconstruct context.
- [ ] Remove the local dialog state from `inventory-page.tsx` and `asset-detail-page.tsx` once the route is wired up.

### 6. Cleanup and verification

- [ ] Stop mounting `ConversionDialog` from the inventory and asset detail routes after the page cutover.
- [ ] Decide whether `components/conversion-dialog.tsx` should be deleted or retained temporarily as a helper extraction source.
- [ ] Verify direct visits with no `asset_ids`, stale `asset_ids`, and unindexed assets all produce friendly blocking states.
- [ ] Verify a conversion that is mid-flight still refreshes correctly after a browser reload.
- [ ] Verify the job and outputs links still work from the new page.

## Status View Behavior

The page should keep the same handoff that the dialog already provides today.

After a successful create:

- show the conversion ID and status
- show the linked job status
- show the output path when available
- show any output files the backend reports
- preserve links to the job detail page and the outputs page

While the conversion or job is still active, the page should poll every 1.5 seconds, just like the current dialog.

## Error And Empty States

The page should be explicit about the common failure cases:

- no assets selected
- one or more selected assets are not indexed
- invalid custom mapping JSON
- invalid resample frequency
- conversion creation failure

The empty state for a direct `/convert` visit without selection should guide the user back to inventory or asset detail rather than pretending the page can function without context.

## Risks And Tradeoffs

### Long Query Strings

Passing selected asset IDs in the URL is simple and shareable, but very large selections could make the URL long.

That is acceptable for phase 1 because the page is primarily launched from asset detail or a modest visible selection. If the selection size becomes a problem later, we can move the selection payload to a short-lived token or session storage bridge.

### Direct Access Without Context

The new route is only useful when it knows which assets to convert.

That is a product tradeoff worth making for phase 1 because it keeps the implementation small and preserves the current launch flow.

### Refresh During Creation

The current dialog loses its post-submit state on refresh.

Using `conversion_id` in the route fixes that and is one of the main reasons to move to a page.

## Acceptance Criteria

The migration is complete when all of these are true:

- inventory and asset detail no longer open a conversion dialog
- the conversion flow lives on a dedicated page route
- selected assets are preserved in the URL
- created conversions can be reopened after refresh
- active conversions continue to poll while the page is open
- the page still links to the job detail and outputs surfaces
