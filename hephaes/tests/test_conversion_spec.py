"""Tests for the richer converter configuration models."""

from __future__ import annotations

from hephaes import (
    ConversionSpec,
    MappingTemplate,
    ResampleConfig,
    TFRecordOutputConfig,
    build_doom_ros_train_py_compatible,
    build_legacy_conversion_spec,
)


def test_conversion_spec_parses_design_example_shape():
    payload = {
        "schema": {"name": "doom_ros_train_py_compatible", "version": 1},
        "input": {
            "paths": ["data/**/*.mcap"],
            "recursive": True,
            "include_topics": ["/doom_image", "/joy"],
        },
        "decoding": {
            "topics": {
                "/doom_image": {"type_hint": "custom_msgs/msg/RawImageBGRA"},
                "/joy": {"type_hint": "sensor_msgs/msg/Joy"},
            },
            "on_decode_failure": "warn",
        },
        "assembly": {
            "trigger_topic": "/doom_image",
            "joins": [
                {
                    "topic": "/joy",
                    "sync_policy": "last-known-before",
                    "staleness_ns": 250_000_000,
                    "required": True,
                }
            ],
        },
        "features": {
            "image": {
                "source": {"topic": "/doom_image", "field_path": "data"},
                "dtype": "bytes",
                "required": True,
                "transforms": [
                    {"image_color_convert": {"from": "bgra", "to": "rgb"}},
                    {"image_encode": {"format": "png"}},
                ],
            },
            "buttons": {
                "source": {"topic": "/joy", "field_path": "buttons"},
                "dtype": "int64",
                "shape": [15],
                "required": True,
                "missing": "zeros",
                "transforms": [{"cast": {"dtype": "int64"}}],
            },
        },
        "labels": {"primary": "buttons"},
        "output": {
            "format": "tfrecord",
            "compression": "gzip",
            "shards": 8,
            "filename_template": "{split}-{shard:05d}-of-{num_shards:05d}.tfrecord",
        },
        "validation": {
            "sample_n": 128,
            "fail_fast": True,
            "bad_record_budget": 0,
            "expected_features": ["image", "buttons"],
        },
    }

    spec = ConversionSpec.model_validate(payload)

    assert spec.schema.name == "doom_ros_train_py_compatible"
    assert spec.schema.version == 1
    assert spec.input.include_topics == ["/doom_image", "/joy"]
    assert spec.decoding.topics["/doom_image"].type_hint == "custom_msgs/msg/RawImageBGRA"
    assert spec.assembly is not None
    assert spec.assembly.trigger_topic == "/doom_image"
    assert spec.assembly.joins[0].sync_policy == "last-known-before"
    assert spec.features["image"].transforms[0].kind == "image_color_convert"
    assert spec.features["image"].transforms[0].params == {"from": "bgra", "to": "rgb"}
    assert spec.features["buttons"].shape == [15]
    assert spec.features["buttons"].missing == "zeros"
    assert spec.validation.expected_features == ["image", "buttons"]
    assert spec.output.format == "tfrecord"
    assert spec.output.compression == "gzip"
    assert spec.output.shards == 8
    assert spec.uses_schema_aware_path is True


def test_legacy_conversion_spec_keeps_compatibility_fields():
    mapping = MappingTemplate.model_validate({"cmd_vel": ["/cmd_vel"]})
    spec = build_legacy_conversion_spec(
        mapping=mapping,
        output=TFRecordOutputConfig(compression="gzip"),
        resample=ResampleConfig(freq_hz=10.0, method="downsample"),
        write_manifest=False,
    )

    assert spec.schema.name == "legacy_mapping"
    assert spec.mapping == mapping
    assert spec.resample is not None
    assert spec.resample.freq_hz == 10.0
    assert spec.output.format == "tfrecord"
    assert spec.output.compression == "gzip"
    assert spec.input.include_topics == ["/cmd_vel"]
    assert spec.write_manifest is False
    assert spec.to_output_config().compression == "gzip"
    assert spec.uses_schema_aware_path is False


def test_doom_preset_exposes_training_contract():
    spec = build_doom_ros_train_py_compatible()

    assert spec.schema.name == "doom_ros_train_py_compatible"
    assert spec.assembly is not None
    assert spec.assembly.trigger_topic == "/doom_image"
    assert spec.features["image"].source.topic == "/doom_image"
    assert spec.features["buttons"].shape == [15]
    assert spec.labels is not None
    assert spec.labels.primary == "buttons"
    assert spec.output.format == "tfrecord"
    assert spec.output.compression == "gzip"
    assert spec.validation.bad_record_budget == 0
    assert spec.uses_schema_aware_path is True
