# Backend

## Install

From `backend/`:

```bash
python -m pip install -e ../hephaes
python -m pip install -e ".[dev]"
```

Or from the repository root:

```bash
python -m pip install -r requirements.txt
```

## Run

From `backend/`:

```bash
python -m uvicorn app.main:app --reload
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
