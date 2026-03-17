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

## Tasks

### Database schema

- Add a `tags` table in [backend/app/db/models.py](/Users/danielyoo/workspace/hephaes/backend/app/db/models.py) with stable IDs, unique tag names, and creation timestamps.
- Add an `asset_tags` join table in [backend/app/db/models.py](/Users/danielyoo/workspace/hephaes/backend/app/db/models.py) with foreign keys to `assets` and `tags`.
- Enforce uniqueness on `(asset_id, tag_id)` so the same tag cannot be attached twice to one asset.
- Decide whether tag names are case-sensitive or normalized to a canonical lowercase form, and keep that behavior explicit in both schema and service logic.
- Add the ORM relationships needed so assets can expose tags and tags can expose linked assets without manual join assembly everywhere.

### Service layer

- Add tag-focused service helpers for:
  - listing tags
  - creating a tag
  - attaching a tag to an asset
  - removing a tag from an asset
- Keep route handlers thin by pushing duplicate detection, normalization, and existence checks into the service layer.
- Return clear domain errors for:
  - duplicate tag names
  - missing assets
  - missing tags
  - duplicate asset-tag attachments

### API schemas

- Extend [backend/app/schemas/assets.py](/Users/danielyoo/workspace/hephaes/backend/app/schemas/assets.py) with typed tag response models.
- Add request and response schemas for:
  - `GET /tags`
  - `POST /tags`
  - `POST /assets/{asset_id}/tags`
  - `DELETE /assets/{asset_id}/tags/{tag_id}`
- Update the asset detail response shape so `GET /assets/{asset_id}` includes the current tags for that asset.
- Keep tag payloads minimal and frontend-friendly, for example `id`, `name`, and `created_at`.

### Route implementation

- Add a dedicated tag router or extend the existing asset routes with the phase 4 tag endpoints.
- Implement `GET /tags` with stable ordering, such as alphabetical by name.
- Implement `POST /tags` with validation, duplicate protection, and a clear `409` or equivalent conflict response for existing names.
- Implement `POST /assets/{asset_id}/tags` so it attaches an existing tag to an asset.
- Implement `DELETE /assets/{asset_id}/tags/{tag_id}` so it cleanly removes an attachment and returns a sensible success response.

### Asset detail integration

- Update asset detail assembly so tags are included whenever an asset is fetched.
- Keep detail payload construction centralized so tags, metadata, and later additions do not drift across routes.
- Make sure tag reads do not accidentally introduce N+1 query patterns when detail pages are loaded repeatedly.

### Search integration

- Extend `GET /assets` query handling to accept a tag filter, for example `tag`.
- Implement the SQLite join needed to filter assets by tag name.
- Define whether tag filtering is exact-match, case-insensitive exact-match, or substring-based, and document that behavior.
- Ensure tag filters compose cleanly with the existing phase 3 filters for filename, type, status, and metadata ranges.

### Tests

- Add backend tests for tag creation.
- Add tests for duplicate tag-name handling.
- Add tests for attaching a tag to an asset.
- Add tests for preventing duplicate tag attachments.
- Add tests for removing tags from assets.
- Add tests confirming `GET /assets/{asset_id}` includes tags.
- Add tests confirming `GET /assets?tag=...` filters correctly and composes with existing phase 3 filters.

### Local verification

- Run the backend locally and create a few tags with overlapping assets.
- Confirm tags can be created, attached, detached, and listed through the API.
- Confirm asset detail responses include tags after attachment.
- Confirm asset list queries narrow correctly by tag while preserving the existing phase 3 search and filtering behavior.
