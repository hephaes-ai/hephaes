# Backend

## Install

From the repository root:

```bash
pip install -e ".[dev,backend]"
```

If you do not need the dev extras:

```bash
pip install ".[backend]"
```

## Run

From the repository root:

```bash
uvicorn backend.app.main:app --reload
```

The health endpoint is available at:

```text
http://127.0.0.1:8000/health
```

## Test

From the repository root:

```bash
pytest backend/tests -q
```
