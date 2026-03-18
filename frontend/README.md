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

Then start the frontend:

```bash
cd frontend
npm run dev
```

The frontend defaults to talking to:

```text
http://127.0.0.1:8000
```

If you need a different backend URL, set:

```bash
NEXT_PUBLIC_BACKEND_BASE_URL=http://127.0.0.1:8000
```

## Checks

From `frontend/`:

```bash
npm run lint
npm run typecheck
npm run build
```

## Notes

- The inventory supports four ingestion flows:
  - file-path registration through `POST /assets/register`
  - native file picker registration through `POST /assets/register-dialog`
  - browser uploads through `POST /assets/upload`
  - directory scanning through `POST /assets/scan-directory`
- The app uses shadcn components and supports light and dark mode from the header toggle.
