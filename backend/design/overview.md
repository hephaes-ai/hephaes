# Backend Overview

## Docs In This Directory

- [architecture.md](./architecture.md): stack, app bootstrap, routing, module boundaries, and execution model
- [data-model-and-storage.md](./data-model-and-storage.md): SQLite schema, JSON-backed records, output directories, and persistence strategy
- [assets-indexing-and-tags.md](./assets-indexing-and-tags.md): ingestion, asset listing/detail, indexing, metadata extraction, and tag behavior
- [jobs-conversions-playback-and-visualization.md](./jobs-conversions-playback-and-visualization.md): durable jobs, conversions, episode playback APIs, and Rerun visualization prep
- [testing-and-operations.md](./testing-and-operations.md): test structure, local operation, environment variables, and current implementation constraints

## Current API Map

- `GET /health`
- `POST /assets/register`
- `POST /assets/upload`
- `POST /assets/register-dialog`
- `POST /assets/scan-directory`
- `POST /assets/{asset_id}/index`
- `POST /assets/{asset_id}/tags`
- `DELETE /assets/{asset_id}/tags/{tag_id}`
- `POST /assets/reindex-all`
- `GET /assets`
- `GET /assets/{asset_id}/episodes`
- `GET /assets/{asset_id}`
- `GET /assets/{asset_id}/episodes/{episode_id}`
- `GET /assets/{asset_id}/episodes/{episode_id}/timeline`
- `GET /assets/{asset_id}/episodes/{episode_id}/samples`
- `POST /conversions`
- `GET /conversions`
- `GET /conversions/{conversion_id}`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `GET /tags`
- `POST /tags`
- `POST /assets/{asset_id}/episodes/{episode_id}/prepare-visualization`
- `GET /assets/{asset_id}/episodes/{episode_id}/viewer-source`
- static artifact serving under `/visualizations/...`

## Code Map

- `app/main.py`: FastAPI app creation, lifespan, router registration, CORS, and static artifact mount
- `app/config.py`: local settings and path/version resolution
- `app/db/`: SQLAlchemy models and session wiring
- `app/api/`: HTTP routers only
- `app/schemas/`: Pydantic request and response models
- `app/services/`: application logic for assets, indexing, tags, jobs, conversions, playback, and visualization
- `tests/`: API-focused tests using FastAPI `TestClient`
