# Hephaes

Python package for turning raw ROS/MCAP logs into standardized datasets.

Supports ROS1 `.bag` and ROS2 `.mcap` inputs. Outputs Parquet or TFRecord — one file per log. Runs locally, no cloud required.

## Installation

```bash
pip install hephaes
```

From source:

```bash
pip install -e ".[dev]"
```

## Three ways to use it

| | Best for |
|---|---|
| **CLI** | Interactive workspace-backed authoring |
| **Workspace API** | Durable workflow state from Python |
| **Direct conversion** | Scripted one-off conversions with a known spec |

---

## CLI

Initialize a workspace, register a log, and launch the interactive wizard:

```bash
hephaes init ./demo
hephaes add --workspace ./demo ./logs/run_001.mcap
hephaes drafts wizard --workspace ./demo <asset-id>
```

Fully scriptable path:

```bash
hephaes drafts create --workspace ./demo <asset-id> --topic /camera --trigger-topic /camera
hephaes drafts preview --workspace ./demo <draft-id> --sample-n 5
hephaes drafts confirm --workspace ./demo <draft-id> --yes
hephaes drafts save-config --workspace ./demo <draft-id> --name camera-demo
hephaes convert --workspace ./demo <asset-id> --config camera-demo
```

`hephaes add` records the canonical file path — it does not copy the raw log.

---

## Workspace API

```python
from hephaes.conversion.draft_spec import DraftSpecRequest
from hephaes.conversion.introspection import InspectionRequest
from hephaes.workspace import Workspace

workspace = Workspace.init("demo", exist_ok=True)
asset = workspace.register_asset("./logs/run_001.mcap")

draft = workspace.create_conversion_draft(
    asset.id,
    inspection_request=InspectionRequest(topics=["/camera"], sample_n=8),
    draft_request=DraftSpecRequest(
        trigger_topic="/camera",
        selected_topics=["/camera"],
        output_format="tfrecord",
        output_compression="none",
    ),
)

draft = workspace.preview_conversion_draft(draft.id, sample_n=5)
draft = workspace.confirm_conversion_draft(draft.id)
config = workspace.save_conversion_config_from_draft(draft.id, name="camera-demo")
outputs = workspace.run_conversion(asset.id, saved_config_selector=config.name)

print(outputs[0].output_path)
```

---

## Direct conversion

Use this when you already have a stable topic mapping and just want to run a conversion.

**Inspect a log:**

```python
from hephaes import Profiler

profile = Profiler(["data/run_001.mcap"], max_workers=1).profile()[0]
print(profile.duration_seconds)
print([(t.name, t.message_type, t.rate_hz) for t in profile.topics])
```

**Define a schema mapping:**

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

Each field lists fallback source topics in priority order — useful when topic names vary across robots or recording setups.

**Convert:**

```python
from hephaes import Converter, ResampleConfig, TFRecordOutputConfig

converter = Converter(
    ["data/run_001.mcap"],
    mapping,
    output_dir="dataset/processed",
    output=TFRecordOutputConfig(),
    resample=ResampleConfig(freq_hz=10.0, method="interpolate"),
    max_workers=1,
)

dataset_paths = converter.convert()
print(dataset_paths[0])
```

**Stream rows:**

```python
from hephaes import stream_tfrecord_rows

for row in stream_tfrecord_rows(dataset_paths[0]):
    print(row)
    break
```

---

## Synchronization modes

| Mode | Config | Behavior |
|---|---|---|
| Preserve timestamps | `resample=None` | Rows at the union of all observed message timestamps |
| Downsample | `ResampleConfig(freq_hz=10.0, method="downsample")` | Regular grid, latest payload per bucket |
| Interpolate | `ResampleConfig(freq_hz=10.0, method="interpolate")` | Regular grid, linearly interpolated numeric leaves |

Interpolation is intended for numeric sensor payloads. Non-numeric leaves fall back to the nearest earlier sample.

---

## Direct log access

```python
from hephaes import RosReader

with RosReader.open("data/run_001.bag") as reader:
    print(reader.topics)
    for message in reader.read_messages(topics=["/cmd_vel"]):
        print(message.timestamp, message.topic, message.data)
        break
```

---

## Development

```bash
cd hephaes
pytest
```
