# Hephaes

Python package for turning raw ROS/MCAP logs into standardized datasets with consistent schemas across runs.

`hephaes` can be used three ways:

- as a CLI for local workspace-backed authoring and conversion
- as a Python `Workspace` API for durable package-owned workflows
- as lower-level conversion helpers when you already have a stable spec

The package helps you:

- ingest ROS1 `.bag` and ROS2 `.mcap` logs
- inspect topics, rates, and recording time ranges
- create draft conversion specs from real logs
- preview and confirm those drafts before saving
- save reusable conversion configs in a local workspace
- synchronize asynchronous sensor streams onto a shared timeline (downsample or interpolate)
- convert logs into wide dataset files such as Parquet and TFRecord
- standardize dataset schemas with explicit topic-to-field mappings

## Current Scope

The package is intentionally focused on the local dataset-prep path.

- Input formats: ROS1 `.bag`, ROS2 `.mcap`
- Input paths must be files, not bag directories
- Assets stay at their original file paths; the workspace records canonical source paths instead of copying raw logs
- Output formats: one wide Parquet or TFRecord file per input log
- Interface: Python library and CLI
- Python: 3.11+
- Local `.hephaes` workspace for assets, drafts, configs, runs, jobs, and outputs

If you need the same dataset schema across different robots or recording setups, you can map multiple possible source topics to the same target field. The converter will use the first topic that exists in each log.

## Installation

Install from pypi:
```bash
pip install hephaes
```

Install from source:

```bash
cd hephaes
python -m pip install .
```

For local development and tests:

```bash
cd hephaes
python -m pip install -e ".[dev]"
```

## CLI Quick Start

Initialize a workspace, register a log by path, and launch the interactive draft wizard:

```bash
hephaes init ./demo
hephaes add --workspace ./demo ./logs/run_001.mcap
hephaes drafts wizard --workspace ./demo <asset-id>
```

If you want the fully scriptable path instead:

```bash
hephaes init ./demo
hephaes add --workspace ./demo ./logs/run_001.mcap
hephaes drafts create --workspace ./demo <asset-id> --topic /camera --trigger-topic /camera
hephaes drafts preview --workspace ./demo <draft-id> --sample-n 5
hephaes drafts confirm --workspace ./demo <draft-id> --yes
hephaes drafts save-config --workspace ./demo <draft-id> --name camera-demo
hephaes convert --workspace ./demo <asset-id> --config camera-demo
```

`hephaes add` stores the canonical file path in the workspace.
It does not copy the raw log into `.hephaes`.

## Workspace API Quick Start

Use `Workspace` when another Python integration needs durable package-owned workflow state:

```python
from hephaes.conversion.draft_spec import DraftSpecRequest
from hephaes.conversion.introspection import InspectionRequest
from hephaes.workspace import Workspace

workspace = Workspace.init("demo", exist_ok=True)
asset = workspace.register_asset("./logs/run_001.mcap")

draft = workspace.create_conversion_draft(
    asset.id,
    inspection_request=InspectionRequest(
        topics=["/camera"],
        sample_n=8,
    ),
    draft_request=DraftSpecRequest(
        trigger_topic="/camera",
        selected_topics=["/camera"],
        output_format="tfrecord",
        output_compression="none",
        max_features_per_topic=2,
    ),
)

draft = workspace.preview_conversion_draft(draft.id, sample_n=5)
draft = workspace.confirm_conversion_draft(draft.id)
config = workspace.save_conversion_config_from_draft(draft.id, name="camera-demo")
outputs = workspace.run_conversion(asset.id, saved_config_selector=config.name)

print(config.id, config.name)
print(outputs[0].output_path)
```

## Direct Conversion Quick Start

Use these lower-level APIs when you already have a stable mapping/spec and just want execution.

Use `Profiler` to inspect timing metadata and topic inventory before deciding how to map the log.

```python
from hephaes import Profiler

profile = Profiler(["data/run_001.mcap"], max_workers=1).profile()[0]

print(profile.ros_version)
print(profile.duration_seconds)
print(profile.start_time_iso, profile.end_time_iso)
print([(topic.name, topic.message_type, topic.rate_hz) for topic in profile.topics])
```

### 1. Define a standardized schema

You can auto-generate a mapping from discovered topics:

```python
from hephaes import build_mapping_template

mapping = build_mapping_template(profile.topics)
print(mapping.root)
```

Or define a stable schema explicitly. This is the main mechanism for dataset schema standardization.

```python
from hephaes import build_mapping_template_from_json

mapping = build_mapping_template_from_json(
    profile.topics,
    {
        "front_camera": ["/camera/front/image_raw", "/sensors/front_cam"],
        "imu": ["/imu/data", "/sensors/imu"],
        "vehicle_twist": ["/cmd_vel", "/vehicle/twist"],
    },
    strict_unknown_topics=False,
)
```

In the example above, `front_camera`, `imu`, and `vehicle_twist` become the canonical dataset fields. Each field can list fallback source topics, which is useful when topic names vary across robots, fleets, or recording versions.

### 2. Convert logs into Parquet or TFRecord

Use `Converter` to write one dataset file per input log. Parquet remains the default.

```python
from hephaes import Converter, ResampleConfig, TFRecordOutputConfig

converter = Converter(
    ["data/run_001.mcap"],
    mapping,
    output_dir="dataset/processed",
    output=TFRecordOutputConfig(),
    resample=ResampleConfig(freq_hz=10.0, method="interpolate"),
    robot_context={"robot_id": "alpha-01", "platform": "spot"},
    max_workers=1,
)

dataset_paths = converter.convert()
print(dataset_paths[0])
print(dataset_paths[0].with_suffix(".manifest.json"))
```

### 3. Stream the output rows

```python
from hephaes import stream_tfrecord_rows

for row in stream_tfrecord_rows(dataset_paths[0]):
    print(row)
    break
```

### 4. Choose image payload contract mode

TFRecord defaults to `image_payload_contract="bytes_v2"`, which writes image `data` fields as raw bytes features while keeping image metadata fields.

```python
from hephaes import TFRecordOutputConfig

output = TFRecordOutputConfig(
    image_payload_contract="bytes_v2",  # default
)
```

For backwards-compatible reads/writes during migration windows, use legacy list-based behavior:

```python
from hephaes import TFRecordOutputConfig

legacy_output = TFRecordOutputConfig(
    image_payload_contract="legacy_list_v1",
)
```

To migrate an existing loaded spec between modes:

```python
from hephaes import load_conversion_spec, set_tfrecord_image_payload_contract

spec = load_conversion_spec("conversion-spec.yaml")
spec = set_tfrecord_image_payload_contract(spec, contract="bytes_v2")
```

## Synchronization Modes

`hephaes` supports three practical ways to align asynchronous topics:

| Mode | Configuration | Behavior |
| --- | --- | --- |
| Preserve original timestamps | `resample=None` | Writes rows at the union of observed message timestamps. |
| Downsample to a fixed rate | `ResampleConfig(freq_hz=10.0, method="downsample")` | Buckets messages on a regular grid and keeps the latest payload seen in each bucket. |
| Interpolate to a fixed rate | `ResampleConfig(freq_hz=10.0, method="interpolate")` | Builds a regular timestamp grid and linearly interpolates numeric JSON leaves between samples. |

Interpolation is intended for numeric sensor payloads. Non-numeric leaves fall back to the earlier sample.

For Parquet output, preserve/downsample modes store raw message bytes as base64-wrapped JSON strings, while interpolate stores normalized JSON payloads derived from deserialized messages. For TFRecord output, all modes deserialize messages and emit flattened typed features.

## Output Format

Each input log becomes one dataset file named like:

```text
episode_0001.parquet
episode_0002.parquet
episode_0003.tfrecord
episode_0001.manifest.json
```

The logical row schema is wide and simple:

```text
timestamp_ns: int64
front_camera: string
imu: string
vehicle_twist: string
...
```

Notes:

- `timestamp_ns` is always present.
- Parquet keeps one nullable column per mapping target.
- TFRecord expands each mapping target into flattened typed feature names such as `imu__orientation__x`.
- Parquet stores each mapped field as a JSON string column.
- Raw byte payloads are wrapped as base64-encoded JSON objects shaped like `{"__bytes__": true, "encoding": "base64", "value": "..."}`.
- TFRecord stores flattened typed features derived from deserialized messages.
- TFRecord uses `float_list`, `int64_list`, and `bytes_list` features, plus companion `<field>__present` flags for nulls.
- Image-like payload bytes are written as raw `bytes_list` features alongside their metadata fields.
- Each converted episode also gets a sidecar manifest at `<episode_id>.manifest.json` for indexing and provenance.
- The manifest includes source metadata, temporal metadata, resolved mapping info, and optional user-supplied `robot_context`.
- The `labels` and `privacy` sections are present by default; placeholder fields such as `auto_tags`, `vlm_description`, `objects_detected`, and `anonymization_method` remain `null` until those features are implemented.

This makes the output easy to stream, inspect, and hand off to downstream ETL, analysis or ML pipelines while preserving source payload fidelity.

## Direct Log Access

If you want to read logs directly instead of converting them immediately, use `RosReader`.

```python
from hephaes import RosReader

with RosReader.open("data/run_001.bag") as reader:
    print(reader.topics)

    for message in reader.read_messages(topics=["/cmd_vel"]):
        print(message.timestamp, message.topic, message.data)
        break

    for topic, timestamp in reader.iter_message_headers(
        topics=["/camera/front/image_raw"],
        start_ns=1_700_000_000_000_000_000,
        stop_ns=1_700_000_000_500_000_000,
    ):
        print(topic, timestamp)
        break
```

## Development

Run the test suite with:

```bash
cd hephaes
pytest
```

Build a wheel locally with:

```bash
cd hephaes
python -m build
```
