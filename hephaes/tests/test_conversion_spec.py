"""Tests for the richer converter configuration models."""

from __future__ import annotations

from hephaes import (
    ConcatSourceSpec,
    ConversionSpec,
    DraftOriginSpec,
    MappingTemplate,
    MetadataSourceSpec,
    PerMessageRowStrategySpec,
    ResampleConfig,
    RowStrategySpec,
    StackSourceSpec,
    TFRecordOutputConfig,
    build_doom_ros_train_py_compatible,
    build_legacy_conversion_spec,
    build_single_trigger_sensor_log_template,
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
    assert spec.row_strategy is not None
    assert spec.row_strategy.kind == "trigger"
    assert spec.assembly.trigger_topic == "/doom_image"
    assert spec.assembly.joins[0].sync_policy == "last-known-before"
    assert spec.assembly.joins[0].default_value == {"buttons": [0] * 15}
    assert spec.features["image"].transforms[0].kind == "image_color_convert"
    assert spec.features["image"].transforms[0].params == {"from": "bgra", "to": "rgb"}
    assert spec.features["buttons"].shape == [15]
    assert spec.features["buttons"].missing == "zeros"
    assert spec.validation.expected_features == ["image", "buttons"]
    assert spec.output.format == "tfrecord"
    assert spec.output.compression == "gzip"
    assert spec.output.image_payload_contract == "bytes_v2"
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
    assert spec.output.image_payload_contract == "bytes_v2"
    assert spec.input.include_topics == ["/cmd_vel"]
    assert spec.write_manifest is False
    assert spec.to_output_config().compression == "gzip"
    assert spec.to_output_config().image_payload_contract == "bytes_v2"
    assert spec.uses_schema_aware_path is False
    assert spec.row_strategy is None


def test_doom_preset_exposes_training_contract():
    spec = build_doom_ros_train_py_compatible()

    assert spec.schema.name == "doom_ros_train_py_compatible"
    assert spec.assembly is not None
    assert spec.row_strategy is not None
    assert spec.assembly.trigger_topic == "/doom_image"
    assert spec.features["image"].source.topic == "/doom_image"
    assert spec.features["buttons"].shape == [15]
    assert spec.labels is not None
    assert spec.labels.primary == "buttons"
    assert spec.output.format == "tfrecord"
    assert spec.output.compression == "gzip"
    assert spec.output.image_payload_contract == "bytes_v2"
    assert spec.validation.bad_record_budget == 0
    assert spec.uses_schema_aware_path is True


def test_conversion_spec_accepts_explicit_row_strategy_without_assembly():
    spec = ConversionSpec.model_validate(
        {
            "schema": {"name": "per_message_demo", "version": 1},
            "row_strategy": {"kind": "per-message", "topic": "/joy"},
            "features": {
                "buttons": {
                    "source": {"kind": "path", "topic": "/joy", "field_path": "buttons"},
                    "dtype": "json",
                }
            },
            "output": {"format": "tfrecord"},
        }
    )

    assert isinstance(spec.row_strategy, PerMessageRowStrategySpec)
    assert spec.row_strategy.topic == "/joy"
    assert spec.assembly is None
    assert spec.uses_schema_aware_path is True


def test_feature_sources_accept_composed_variants():
    spec = ConversionSpec.model_validate(
        {
            "schema": {"name": "composed_sources", "version": 1},
            "row_strategy": {"kind": "trigger", "trigger_topic": "/camera"},
            "features": {
                "metadata_tag": {
                    "source": {"kind": "metadata", "key": "episode_id"},
                    "dtype": "json",
                },
                "stacked": {
                    "source": {
                        "kind": "stack",
                        "sources": [
                            {"topic": "/camera", "field_path": "left"},
                            {"kind": "constant", "value": [0, 0, 0]},
                        ],
                    },
                    "dtype": "json",
                },
                "concatenated": {
                    "source": {
                        "kind": "concat",
                        "sources": [
                            {"topic": "/camera", "field_path": "vector_a"},
                            {"topic": "/camera", "field_path": "vector_b"},
                        ],
                    },
                    "dtype": "json",
                },
            },
            "draft_origin": {
                "kind": "inspection",
                "source_topics": ["/camera"],
                "assumptions": ["sampled from one topic"],
            },
            "output": {"format": "tfrecord"},
        }
    )

    assert isinstance(spec.features["metadata_tag"].source, MetadataSourceSpec)
    assert isinstance(spec.features["stacked"].source, StackSourceSpec)
    assert isinstance(spec.features["concatenated"].source, ConcatSourceSpec)
    assert isinstance(spec.draft_origin, DraftOriginSpec)


def test_row_strategy_type_alias_is_runtime_visible():
    assert RowStrategySpec is not None


def test_single_trigger_template_provides_runnable_starter():
    spec = build_single_trigger_sensor_log_template(
        trigger_topic="/camera/front/image_raw",
        join_topics=["/imu/data"],
    )

    assert spec.schema.name == "single_trigger_sensor_log"
    assert spec.assembly is not None
    assert spec.assembly.trigger_topic == "/camera/front/image_raw"
    assert [join.topic for join in spec.assembly.joins] == ["/imu/data"]
    assert spec.assembly.joins[0].required is False
    assert spec.features["camera_front_image_raw"].source.topic == "/camera/front/image_raw"
    assert spec.features["imu_data"].source.topic == "/imu/data"
    assert spec.validation.expected_features == ["camera_front_image_raw", "imu_data"]
    assert spec.output.format == "tfrecord"
