# Frontend Phase 4

## Goal

Add tag management and complete the bulk-selection interaction model.

## Depends On

- [backend-phase4.md](/Users/danielyoo/workspace/hephaes/design/backend-phase4.md)
- [frontend-ui-guidelines.md](/Users/danielyoo/workspace/hephaes/design/frontend-ui-guidelines.md)

## Product Scope

Implement:

- tag creation
- tag assignment and removal on individual assets
- bulk tag application for selected assets
- tags in inventory rows
- tags in the asset detail view
- filtering by tag
- stronger bulk selection UX

Tag interactions should stay lightweight and minimal. Prefer shadcn popovers, dialogs, badges, and command-style pickers over custom-heavy controls.

## Recommended UI Surfaces

### Inventory page

- persistent row selection model
- bulk actions toolbar
- tag chips in rows
- tag filter control

### Asset detail page

- tag list
- add-tag interaction
- remove-tag interaction

### Shared tag UI

- tag picker with existing tags
- duplicate-tag handling or warnings

## State and Data Guidance

Selection state should remain stable where practical while filtering and browsing.

Recommended behavior:

- show clear selected-count feedback
- let users clear selection quickly
- indicate when a bulk action applies only to selected items
- preserve selection only when it remains understandable to the user

## Backend Endpoints Used

- `GET /tags`
- `POST /tags`
- `POST /assets/{asset_id}/tags`
- `DELETE /assets/{asset_id}/tags/{tag_id}`
- `GET /assets`
- `GET /assets/{asset_id}`

## Deliverable

By the end of phase 4, a user should be able to:

- create and manage tags
- apply tags from both inventory and detail views
- use bulk selection for index and tag workflows
- filter inventory results by tag

## Tasks

### API integration

- Extend the frontend API layer to support:
  - `GET /tags`
  - `POST /tags`
  - `POST /assets/{asset_id}/tags`
  - `DELETE /assets/{asset_id}/tags/{tag_id}`
- Update typed asset detail responses so tags are treated as first-class data instead of `unknown` extras.
- Add tag-aware request helpers in [frontend/lib/api.ts](/Users/danielyoo/workspace/hephaes/frontend/lib/api.ts).
- Update shared cache invalidation so inventory, detail, and tag-list queries stay in sync after tag changes.

### Shared tag UI

- Add minimal shadcn-first tag primitives such as:
  - tag badges
  - a tag picker or command-style list
  - a compact create-tag flow
- Prefer restrained popovers, dialogs, or dropdown surfaces over large dedicated panels.
- Handle duplicate tag creation attempts cleanly with inline feedback rather than noisy success messaging.
- Keep the visual treatment minimal so tags read like lightweight metadata, not primary page chrome.

### Inventory tag presentation

- Add tag chips or badges to inventory rows without overwhelming the main table layout.
- Decide how many tags appear inline before collapsing into a `+N` overflow indicator.
- Ensure row tags work well in both light and dark mode and remain readable at table density.
- Preserve the table-first layout from earlier phases rather than expanding rows into card-like blocks.

### Inventory filtering

- Add a tag filter control to the inventory search and filters panel.
- Populate tag filter options from `GET /tags`.
- Make tag filtering URL-backed so inventory state survives refreshes and navigation.
- Keep tag filtering composable with the existing search, type, status, duration, size, and date filters.

### Asset detail tagging

- Replace the placeholder tag area on the asset detail page with the real asset tags from `GET /assets/{asset_id}`.
- Add a compact add-tag interaction on the detail page.
- Add remove-tag affordances for existing tags.
- Show useful empty states when an asset has no tags yet.
- Surface backend errors such as duplicate attachments or missing tags clearly.

### Bulk tag workflows

- Extend the inventory selection toolbar with bulk tag actions for selected assets.
- Support applying an existing tag to the current selection.
- Decide whether phase 4 also supports bulk tag removal or whether that remains a follow-up.
- Keep selection behavior understandable while bulk tag operations complete and data refetches.
- Make it obvious when a bulk action applies only to the current selected result set.

### Selection UX refinement

- Tighten the selected-state UX so indexing and tagging actions can coexist in one compact toolbar.
- Ensure users can clearly see selected counts and clear selection quickly.
- Preserve selection across filter and sort changes only when the result still feels predictable.
- Avoid surprising deselection during background refetches unless rows genuinely leave the visible result set.

### Error and feedback UX

- Show inline or lightweight toast feedback for tag creation failures, duplicate tags, and bulk-action partial failures.
- Keep normal success paths quiet where possible so the UI stays minimal.
- Distinguish between validation errors, not-found errors, and conflict errors when useful.
- Reuse the existing app feedback patterns instead of introducing a second messaging system.

### Local verification

- Run the frontend against the real local backend with phase 4 tagging support enabled.
- Confirm tags can be created from the frontend.
- Confirm tags can be attached and removed from the asset detail page.
- Confirm inventory rows and detail views stay in sync after tag updates.
- Confirm inventory filtering by tag works correctly alongside the existing phase 2 and phase 3 filters.
- Confirm bulk tag application behaves correctly for mixed selections.
