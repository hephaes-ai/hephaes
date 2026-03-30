# Backend

FastAPI service that powers the Hephaes desktop app and local development server.

## Install

```bash
# from repo root
pip install -r requirements.txt

# or individually from backend/
pip install -e ../hephaes
pip install -e ".[dev]"
```

## Run

```bash
# from backend/
python -m uvicorn app.main:app --reload
```

Health check: `http://127.0.0.1:8000/health`

## Test

```bash
# from backend/
pytest tests -q
```

## API

| Prefix | Description |
|---|---|
| `GET /health` | Health check |
| `GET/POST /assets` | Register, scan, list, and index log assets |
| `GET /dashboard` | Summary, trends, and blockers |
| `GET/POST /conversions` | Run and inspect conversions |
| `GET/POST /conversion-configs` | Saved conversion configs |
| `GET /jobs` | Job status and history |
| `GET /outputs` | Browse generated output artifacts |
| `GET/POST /tags` | Tag catalog |

## Configuration

| Variable | Default | Description |
|---|---|---|
| `HEPHAES_BACKEND_DATA_DIR` | `backend/data/` (dev) · `~/.hephaes/backend/` (desktop) | Root data directory |
| `HEPHAES_WORKSPACE_ROOT` | `<data_dir>/workspace/` | Workspace storage path |
| `HEPHAES_BACKEND_RAW_DATA_DIR` | `<data_dir>/raw/` | Staged raw log files |
| `HEPHAES_BACKEND_OUTPUTS_DIR` | `<data_dir>/outputs/` | Conversion output artifacts |
| `HEPHAES_BACKEND_LOG_DIR` | `<data_dir>/logs/` | Uvicorn log files |
| `HEPHAES_DESKTOP_MODE` | `0` | Set to `1` for desktop/sidecar mode |
| `HEPHAES_BACKEND_HOST` | `127.0.0.1` | Bind host |
| `HEPHAES_BACKEND_PORT` | `8000` | Bind port |
| `HEPHAES_BACKEND_DEBUG` | `0` | Enable FastAPI debug mode |
| `HEPHAES_BACKEND_CORS_ALLOW_ORIGIN_REGEX` | `https?://(localhost\|127\.0\.0\.1)(:\d+)?` | CORS origin allowlist |

## Desktop / Sidecar

The Tauri desktop app bundles the backend as a sidecar binary. See `frontend/README.md` for how to stage and run it.

To run the desktop entrypoint directly:

```bash
python -m app.desktop_main --host 127.0.0.1 --port 8000
```

In desktop mode, data is stored under `~/.hephaes/backend/` and logs go to `~/.hephaes/backend/logs/`.
