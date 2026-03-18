# Hephaes Monorepo

This repository is split into three top-level projects:

- `frontend/`: the Next.js UI
- `backend/`: the FastAPI service
- `hephaes/`: the shared Python package

## Python Setup

Install both Python projects for local development from the repository root:

```bash
python -m pip install -r requirements.txt
```

Or install them individually:

```bash
python -m pip install -e "./hephaes[dev]"
python -m pip install -e "./backend[dev]"
```

## Layout

```text
frontend/
backend/
hephaes/
```
