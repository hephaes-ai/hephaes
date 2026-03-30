# Frontend

React + Vite UI with a Tauri desktop shell.

## Install

```bash
cd frontend
npm install
```

## Run

**Web dev** (against a running backend):

```bash
# terminal 1 — from backend/
python -m uvicorn app.main:app --reload

# terminal 2 — from frontend/
npm run dev
```

The frontend talks to `http://127.0.0.1:8000` by default. Override with `VITE_BACKEND_BASE_URL`.

**Desktop dev** (sidecar — stages and starts the backend automatically):

```bash
npm run desktop:tauri-dev
```

**Desktop dev** (external — connect to an already running backend):

```bash
npm run desktop:tauri-dev:external
```

## Build

Web bundle only:

```bash
npm run build
```

Desktop app (stage sidecar first, then bundle):

```bash
npm run tauri:prepare-backend:clean
npm run tauri:build
```

Output: `src-tauri/target/release/bundle/`

## Checks

```bash
npm run lint
npm test
npm run typecheck
npm run build
cargo check --manifest-path src-tauri/Cargo.toml
```

## Logs and data (packaged app)

| Path | Contents |
|---|---|
| `~/Library/Logs/ai.hephaes.desktop/desktop.log` | Tauri shell logs |
| `~/Library/Logs/ai.hephaes.desktop/backend/` | Sidecar backend logs |
| `~/Library/Application Support/ai.hephaes.desktop/backend/` | Database, raw assets, outputs |
