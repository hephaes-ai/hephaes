# hephaes-core

Python package for robotics teams that need to turn raw ROS logs into consistent datasets. The package helps you:

- ingest ROS1 `.bag` and ROS2 `.mcap` logs
- inspect topics, rates, and recording time ranges
- synchronize asynchronous sensor streams onto a shared timeline
- convert logs into wide Parquet datasets
- standardize dataset schemas with explicit topic-to-field mappings

## Current Scope

The library is intentionally focused on the core dataset-prep path.

- Input formats: ROS1 `.bag`, ROS2 `.mcap`
- Input paths must be files, not bag directories
- Output format: one wide Parquet file per input log
- Interface: Python library
- Python: 3.11+

If you need the same dataset schema across different robots or recording setups, you can map multiple possible source topics to the same target field. The converter will use the first topic that exists in each log.

## Installation

Install from source:

```bash
pip install .
```

For local development:

```bash
pip install -e .
```

## Quick Start

### 1. Profile a log

Use `Profiler` to inspect timing metadata and topic inventory before deciding how to map the log.

```python
from hephaes_core import Profiler

profile = Profiler(["data/run_001.mcap"], max_workers=1).profile()[0]

print(profile.ros_version)
print(profile.duration_seconds)
print(profile.start_time_iso, profile.end_time_iso)
print([(topic.name, topic.message_type, topic.rate_hz) for topic in profile.topics])
```

### 2. Define a standardized schema

You can auto-generate a mapping from discovered topics:

```python
from hephaes_core import build_mapping_template

mapping = build_mapping_template(profile.topics)
print(mapping.root)
```

Or define a stable schema explicitly. This is the main mechanism for dataset schema standardization.

```python
from hephaes_core import build_mapping_template_from_json

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

### 3. Convert logs into Parquet

Use `Converter` to write one Parquet file per input log.

```python
from hephaes_core import Converter, ResampleConfig

converter = Converter(
    ["data/run_001.mcap"],
    mapping,
    output_dir="dataset/processed",
    resample=ResampleConfig(freq_hz=10.0, method="interpolate"),
    max_workers=1,
)

parquet_paths = converter.convert()
print(parquet_paths[0])
```

### 4. Stream the output rows

```python
from hephaes_core import stream_wide_parquet_rows

for row in stream_wide_parquet_rows(parquet_paths[0], batch_size=128):
    print(row)
    break
```

## Synchronization Modes

`hephaes-core` supports three practical ways to align asynchronous topics:

| Mode | Configuration | Behavior |
| --- | --- | --- |
| Preserve original timestamps | `resample=None` | Writes rows at the union of observed message timestamps. |
| Downsample to a fixed rate | `ResampleConfig(freq_hz=10.0, method="downsample")` | Buckets messages on a regular grid and keeps the latest payload seen in each bucket. |
| Interpolate to a fixed rate | `ResampleConfig(freq_hz=10.0, method="interpolate")` | Builds a regular timestamp grid and linearly interpolates numeric JSON leaves between samples. |

Interpolation is intended for numeric sensor payloads. Non-numeric leaves fall back to the earlier sample.

When you preserve original timestamps or downsample, the converter stores raw message bytes as base64-wrapped JSON strings. When you interpolate, it stores normalized JSON payloads derived from deserialized messages.

## Output Format

Each input log becomes one Parquet file named like:

```text
episode_0001.parquet
episode_0002.parquet
```

The Parquet schema is wide and simple:

```text
timestamp_ns: int64
front_camera: string
imu: string
vehicle_twist: string
...
```

Notes:

- `timestamp_ns` is always present.
- Each mapping target becomes a nullable string column.
- Payloads are stored as JSON strings.
- Raw byte payloads are wrapped as base64-encoded JSON objects shaped like `{"__bytes__": true, "encoding": "base64", "value": "..."}`.

This makes the output easy to stream, inspect, and hand off to downstream ETL or ML pipelines while preserving source payload fidelity.

## Direct Log Access

If you want to read logs directly instead of converting them immediately, use `RosReader`.

```python
from hephaes_core import RosReader

with RosReader.open("data/run_001.bag") as reader:
    print(reader.topics)

    for message in reader.read_messages(topics=["/cmd_vel"]):
        print(message.timestamp, message.topic, message.data)
        break
```

## Development

Run the test suite with:

```bash
pytest
```

## License

MIT. See [LICENSE](LICENSE).
