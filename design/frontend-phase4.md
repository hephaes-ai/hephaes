# Frontend Phase 4

## Goal

Add tag management and complete the bulk-selection interaction model.

## Depends On

- [backend-phase4.md](/Users/danielyoo/workspace/hephaes/design/backend-phase4.md)

## Product Scope

Implement:

- tag creation
- tag assignment and removal on individual assets
- bulk tag application for selected assets
- tags in inventory rows
- tags in the asset detail view
- filtering by tag
- stronger bulk selection UX

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
