# Frontend

## Install

From the repository root:

```bash
cd frontend
npm install
```

## Run

Start the backend first from the repository root:

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