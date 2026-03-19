# Backend

## Install

From `backend/`:

```bash
python -m pip install -e ../hephaes
python -m pip install -e ".[dev]"
```

The backend replay websocket endpoint requires a websocket transport library.
Installing `backend` from this project now includes `websockets` automatically.

Or from the repository root:

```bash
python -m pip install -r requirements.txt
```

## Run

From `backend/`:

```bash
python -m uvicorn app.main:app --reload
```

If you upgraded from an older checkout, reinstall the backend package once so the
new websocket dependency is present:

```bash
python -m pip install -e ".[dev]"
```

The health endpoint is available at:

```text
http://127.0.0.1:8000/health
```

## Test

From `backend/`:

```bash
pytest tests -q
```
