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

## Conversion Contract Examples

Default TFRecord behavior (image payload bytes-first):

```bash
curl -X POST http://127.0.0.1:8000/conversions \
	-H "Content-Type: application/json" \
	-d '{
		"asset_ids": ["<asset-id>"],
		"output": {
			"format": "tfrecord",
			"compression": "none"
		}
	}'
```

Legacy compatibility behavior (list-based image payload contract):

```bash
curl -X POST http://127.0.0.1:8000/conversions \
	-H "Content-Type: application/json" \
	-d '{
		"asset_ids": ["<asset-id>"],
		"output": {
			"format": "tfrecord",
			"compression": "none",
			"image_payload_contract": "legacy_list_v1"
		}
	}'
```

Filter conversion history by representation mode:

```bash
curl "http://127.0.0.1:8000/conversions?image_payload_contract=bytes_v2"
curl "http://127.0.0.1:8000/conversions?legacy_compatible=true"
```
