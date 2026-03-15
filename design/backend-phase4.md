# Backend Phase 4

## Goal

Add lightweight tagging so users can organize assets locally.

## Scope

Create:

- a `tags` table
- an `asset_tags` join table

Suggested fields:

### `tags`

- `id`
- `name`
- `created_at`

### `asset_tags`

- `asset_id`
- `tag_id`
- unique constraint on `(asset_id, tag_id)`

## API Surface

Add these routes:

- `GET /tags`
- `POST /tags`
- `POST /assets/{asset_id}/tags`
- `DELETE /assets/{asset_id}/tags/{tag_id}`

The asset detail response should now include tags.

`POST /assets/{asset_id}/tags` can start by accepting an existing `tag_id`. If needed, the frontend can create missing tags first with `POST /tags`.

## Search Integration

Update `GET /assets` so assets can be filtered by tags later, for example:

- `GET /assets?tag=night-run`

This can stay as a simple join query in SQLite.

## Deliverable

By the end of phase 4, you should be able to:

- create tags
- attach tags to assets
- remove tags from assets
- include tags in the asset detail page
- filter asset lists by tag
