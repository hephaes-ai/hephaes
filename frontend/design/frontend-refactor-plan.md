# Frontend Refactor Plan

## Motivation

A code review identified structural issues that have grown organically as the frontend expanded. The main problems are:

- **Duplicated utility functions** — identical helpers like `buildAssetDetailHref`, `buildJobDetailHref`, `formatCount`, and `formatSentenceCase` are copy-pasted across 2–4 files each.
- **Duplicated components** — `MetadataField` is defined identically in 3 files, `EmptyState` variants exist in 5 files, and `FormNotice`/`InlineNotice` are near-identical in 2 files.
- **Inline types** — shared interfaces like `ActiveFilterChip` and `FormMessage` are defined separately in multiple page components.
- **Monolith page components** — `inventory-page.tsx` (1,933 lines) and `outputs-page.tsx` (1,667 lines) contain sub-components, helpers, types, form state, filter logic, and API mutations all in one file.
- **Mutation logic outside hooks** — page components call API functions like `indexAsset`, `createConversion`, and `scanDirectoryForAssets` directly instead of going through hooks like the existing `useCreateOutputAction` pattern.

This plan addresses these issues in four phases, ordered so that each phase builds on the previous one and every phase leaves the app in a working state.

---

## Phase 1 — Extract Atomic Components

**Goal:** Eliminate duplicated presentational components by extracting them into `components/`.

### 1a. `MetadataField`

Currently defined identically in three files:
- `components/outputs-page.tsx:407`
- `components/asset-detail-page.tsx:108`
- `components/job-detail-page.tsx:53`

Create `components/metadata-field.tsx`:

```tsx
export function MetadataField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium text-foreground">{value}</dd>
    </div>
  );
}
```

Remove all three inline definitions and import from the new file.

### 1b. `EmptyState`

Five near-identical variants exist:
- `OutputsEmptyState` in `components/outputs-page.tsx:389`
- `InventoryEmptyState` in `components/inventory-page.tsx:297`
- `JobsEmptyState` in `components/jobs-page.tsx:59`
- `DashboardEmptyState` in `components/dashboard-page.tsx:157`
- `MetadataEmptyState` in `components/asset-detail-page.tsx:123`

Create `components/empty-state.tsx` with a single `EmptyState` component:

```tsx
export function EmptyState({
  action,
  description,
  title,
}: {
  action?: React.ReactNode;
  description: string;
  title: string;
}) {
  return (
    <div className="rounded-xl border border-dashed px-6 py-16 text-center">
      <h2 className="text-sm font-medium text-foreground">{title}</h2>
      <p className="mx-auto mt-2 max-w-2xl text-sm text-muted-foreground">{description}</p>
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  );
}
```

Note: `MetadataEmptyState` in `asset-detail-page.tsx` uses slightly different styling (`rounded-lg`, `px-4 py-8`). Either add a `variant` prop (`"card" | "page"`) or keep the asset-detail version as a local override if it truly needs distinct styling.

Replace all five variants with imports from the shared component.

### 1c. `InlineNotice`

Two similar alert wrappers:
- `FormNotice` in `components/inventory-page.tsx:119` (supports `"success" | "info" | "error"`)
- `InlineNotice` in `components/asset-detail-page.tsx:89` (supports `"info" | "error"`)

Create `components/inline-notice.tsx` that supports all three tones. Replace both inline definitions.

### 1d. `OutputAvailabilityBadge`

Currently exported from `components/outputs-page.tsx:422` and imported by `output-detail-page.tsx`. It follows the same pattern as `AssetStatusBadge` and `WorkflowStatusBadge` — it should be its own file.

Create `components/output-availability-badge.tsx` and move the component there.

### Verification

After this phase, run the app and confirm:
- All pages render correctly.
- No duplicate `MetadataField`, `EmptyState`, `InlineNotice`, or badge definitions remain outside their new canonical files.

---

## Phase 2 — Deduplicate Utility Functions

**Goal:** Consolidate scattered helper functions into `lib/` modules.

### 2a. Navigation helpers → `lib/navigation.ts`

`lib/navigation.ts` currently only exports `resolveReturnHref`. Move these functions there:

| Function | Currently defined in |
|---|---|
| `buildAssetDetailHref` | `outputs-page.tsx`, `inventory-page.tsx`, `jobs-page.tsx`, `job-detail-page.tsx` |
| `buildJobDetailHref` | `outputs-page.tsx`, `dashboard-page.tsx`, `asset-detail-page.tsx`, `jobs-page.tsx` |
| `buildOutputDetailHref` | `outputs-page.tsx` |
| `buildHref` (generic URL builder) | `dashboard-page.tsx` |
| `buildInventoryReplayHref` | `inventory-page.tsx` (wraps `buildReplayHref`) |

After moving, delete all local definitions and update imports in every consuming file.

### 2b. Format helpers → `lib/format.ts`

| Function | Action |
|---|---|
| `formatCount` | Defined in `outputs-page.tsx:117` and `inventory-page.tsx:135`. Move to `lib/format.ts`. |
| `formatSentenceCase` | Already in `lib/format.ts:86`. Delete the duplicate in `conversion-dialog.tsx:97`. |
| `formatOutputRole` | Defined in `outputs-page.tsx:121`. Move to `lib/format.ts` alongside the other output formatters. |
| `formatNumber` | Defined in `dashboard-page.tsx:76`. Move to `lib/format.ts`. |

### 2c. Status class helpers

`getConversionStatusClasses` in `conversion-dialog.tsx:101` partially duplicates the color logic in `workflow-status-badge.tsx`. Evaluate whether `WorkflowStatusBadge` can be used directly. If the dialog needs raw class strings rather than a badge component, extract a shared `getWorkflowStatusClasses` utility in `lib/format.ts` and use it in both places.

### Verification

After this phase:
- `grep -r "function buildAssetDetailHref\|function buildJobDetailHref\|function formatCount\|function formatSentenceCase" frontend/components/` should return zero results.
- All navigation helper imports should point to `@/lib/navigation`.

---

## Phase 3 — Centralize Shared Types

**Goal:** Move reused interfaces out of component files into a shared types module.

### 3a. Create `lib/types.ts`

This file holds UI-layer types that are used across multiple components. Domain/API types remain in `lib/api.ts`.

```ts
/** Represents one active filter chip in a URL-driven filter bar. */
export interface ActiveFilterChip {
  key: string;
  label: string;
  /** Search param updates to apply when this chip is removed. */
  updates?: Record<string, string | null>;
}

/** Inline notice state used by form and detail surfaces. */
export interface NoticeMessage {
  description?: string;
  title: string;
  tone: "error" | "info" | "success";
}
```

### 3b. Update consumers

- `inventory-page.tsx`: delete local `ActiveFilterChip` and `FormMessage`, import from `@/lib/types`.
- `outputs-page.tsx`: delete local `ActiveFilterChip` and `OutputPreviewFact`, import `ActiveFilterChip` from `@/lib/types`. Keep `OutputPreviewFact` local if only used in that file.
- `asset-detail-page.tsx`: delete the inline `{ description?; title; tone }` type for `requestMessage` state, import `NoticeMessage` from `@/lib/types`.

### 3c. Hook types

The types in `hooks/use-episode-replay.ts` (`ReplayPlaybackState`, `UseEpisodeReplayResult`, etc.) are consumed by `visualization-page.tsx`. Export them from the hook file so they are part of the public contract, but they do not need to move to `lib/types.ts` since they are specific to the replay hook.

### Verification

After this phase:
- `grep -r "interface ActiveFilterChip" frontend/components/` should return zero results.
- All shared UI types should be importable from `@/lib/types`.

---

## Phase 4 — Decompose Page Orchestrators

**Goal:** Slim down the large `*-page.tsx` components so they focus on orchestration — composing hooks, shared components, and sub-sections — rather than owning everything.

This is the largest phase and should be done one page at a time. Start with the two biggest files.

### 4a. `inventory-page.tsx` (1,933 lines)

Break into:
- **`components/inventory-page.tsx`** — main orchestrator. Owns top-level state, URL param sync, and section layout. Target: ~400–600 lines.
- **`components/inventory-upload-dialog.tsx`** — the upload file dialog and progress state.
- **`components/inventory-scan-dialog.tsx`** — the directory scan dialog and form.
- **`components/inventory-table.tsx`** — the asset table with sorting, selection, and row rendering.
- **`hooks/use-url-filters.ts`** — extract the filter-chip + searchParam sync pattern that is shared with `outputs-page.tsx`. This hook would handle reading params, building `ActiveFilterChip[]`, and providing an `updateParam` helper.

### 4b. `outputs-page.tsx` (1,667 lines)

Break into:
- **`components/outputs-page.tsx`** — main orchestrator. Target: ~400–500 lines.
- **`components/output-detail-content.tsx`** — the `OutputDetailContent` component already exported for `output-detail-page.tsx` to consume. Give it its own file.
- **`components/output-table.tsx`** — the output table/card view with selection and batch actions.
- **`components/output-preview-panel.tsx`** — the metadata preview sidebar.
- Reuse **`hooks/use-url-filters.ts`** from 4a for the filter bar.

### 4c. `visualization-page.tsx` (1,184 lines)

Break into:
- **`components/visualization-page.tsx`** — orchestrator for episode selection, replay controls, and viewer layout.
- **`components/visualization-lane-panel.tsx`** — the lane/stream selection sidebar.
- **`components/visualization-controls.tsx`** — playback controls (play/pause, speed, scrubber).

### 4d. Mutation hooks

Create focused mutation hooks that follow the `useCreateOutputAction` pattern:
- **`hooks/use-index-asset.ts`** — wraps `indexAsset` / `reindexAllAssets` calls.
- **`hooks/use-create-conversion.ts`** — wraps `createConversion` and polling for completion.
- **`hooks/use-scan-directory.ts`** — wraps `scanDirectoryForAssets`.
- **`hooks/use-upload-assets.ts`** — wraps the multi-file upload + progress tracking logic currently inline in `inventory-page.tsx`.

Each hook should handle the loading/error state and call `useBackendCache()` for revalidation, keeping page components free of direct API calls and cache management.

### 4e. Remaining pages

`dashboard-page.tsx` (912 lines), `conversion-dialog.tsx` (873 lines), and `asset-detail-page.tsx` (784 lines) are smaller but can benefit from the same pattern once the first three are done. These can be addressed opportunistically.

### Verification

After this phase:
- No component file in `components/` exceeds ~600 lines.
- Page components primarily compose hooks and sub-components rather than defining them inline.
- `app/**/page.tsx` files remain thin Suspense wrappers (no changes needed here — they already follow this pattern).
- Direct API function calls (`indexAsset`, `createConversion`, `scanDirectoryForAssets`, `uploadAssetFile`) no longer appear in component files; they live exclusively in hooks and `lib/api.ts`.

---

## Execution Notes

- **Each phase is independently shippable.** The app should work correctly after completing any phase, even if later phases haven't started.
- **Test after each sub-step**, not just after each phase. Extract one component, verify the page, then move on.
- **Update `design/shared-components-and-utils.md` and `design/architecture.md`** after phases 1 and 2 to reflect the new shared components and utility locations.
- **Do not change behavior.** Every change in this plan is a structural refactor. No UI behavior, API calls, or user-facing functionality should change.
