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

## Image Payload Contract UX

The conversion and output surfaces now expose backend schema policy metadata so users can confirm TFRecord image payload behavior without inspecting raw files.

- Conversion authoring shows an `Image payload contract` callout with:
  - policy version
  - effective image payload contract (`bytes_v2` or `legacy_list_v1`)
  - payload/null encodings
  - legacy compatibility warnings and mixed-rollout fallback states
- Conversion status and job detail pages show the effective payload contract for the executed run.
- Outputs list/detail pages show payload-contract context and preview facts so users can verify loader expectations quickly.

### Screenshot Checklist

Capture and pin these screenshots when preparing release notes:

1. `/convert/new` with the image payload contract callout in default training mode.
2. `/convert/new` or `/convert/use` showing legacy compatibility warning state.
3. `/jobs/{jobId}` conversion output section showing effective image payload contract.
4. `/outputs` opened from conversion status with `image_payload_contract` filter chip/context alert.
5. `/outputs/{outputId}` preview panel showing `Image payload` fact and loader expectation note.

## Notes

- The inventory supports four ingestion flows:
  - file-path registration through `POST /assets/register`
  - native file picker registration through `POST /assets/register-dialog`
  - browser uploads through `POST /assets/upload`
  - directory scanning through `POST /assets/scan-directory`
- The app uses shadcn components and supports light and dark mode from the header toggle.
