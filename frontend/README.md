# Frontend

## Install

From the repository root:

```bash
cd frontend
npm install
```

## Run

For a frontend-only dev session against an already running backend, start the
backend first from the repository root:

```bash
cd backend
python -m uvicorn app.main:app --reload
```

Then start the desktop frontend:

```bash
cd frontend
npm run tauri:dev
```

The desktop frontend defaults to talking to:

```text
http://127.0.0.1:8000
```

If you need a different desktop backend URL, set:

```bash
VITE_BACKEND_BASE_URL=http://127.0.0.1:8000
```

If `VITE_BACKEND_BASE_URL` is unset, `npm run tauri:dev` will build and launch
the bundled backend sidecar automatically.

If you still need to run the legacy Next.js frontend during migration, use:

```bash
cd frontend
npm run dev
```

and configure it with:

```bash
NEXT_PUBLIC_BACKEND_BASE_URL=http://127.0.0.1:8000
```

## Checks

From `frontend/`:

```bash
npm run lint
npm test
npm run typecheck
npm run build
```

## Package

From `frontend/`:

```bash
npm run tauri:build
```

This build now stages the packaged backend sidecar automatically before the
desktop bundle is created. The macOS app bundle is written to:

```text
src-tauri/target/release/bundle/macos/Hephaes.app
```

and the matching DMG is written to:

```text
src-tauri/target/release/bundle/dmg/
```

## Debugging

The packaged desktop shell writes its own logs to:

```text
~/Library/Logs/ai.hephaes.desktop/desktop.log
```

The bundled FastAPI sidecar writes backend startup and request logs to:

```text
~/Library/Logs/ai.hephaes.desktop/backend/
```

The packaged app stores its local database, raw assets, and generated outputs in:

```text
~/Library/Application Support/ai.hephaes.desktop/backend/
```
