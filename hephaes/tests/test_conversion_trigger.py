"""Tests for trigger-based conversion assembly."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hephaes import Converter
from hephaes.conversion import assemble_trigger_records
from hephaes.models import ConversionSpec, FeatureSpec, FieldSourceSpec, JoinSpec, OutputSpec, SchemaSpec
from hephaes.tfrecord import stream_tfrecord_rows


def _patch_any_reader(mock_reader: MagicMock):
    return patch("hephaes.reader.AnyReader", return_value=mock_reader)


def make_mock_any_reader_with_payloads(
    *,
    topics: dict[str, str],
    messages: list[tuple[str, int, object]],
) -> MagicMock:
    connections = []
    for topic, msgtype in topics.items():
        conn = MagicMock()
        conn.topic = topic
        conn.msgtype = msgtype
        connections.append(conn)

    conn_by_topic = {conn.topic: conn for conn in connections}
    records: list[tuple[str, int, bytes]] = []
    payload_by_raw: dict[bytes, object] = {}
    for idx, (topic, timestamp, payload) in enumerate(messages):
        raw = f"raw-{idx}".encode("ascii")
        records.append((topic, timestamp, raw))
        payload_by_raw[raw] = payload

    mock_reader = MagicMock()
    mock_reader.start_time = records[0][1] if records else None
    mock_reader.end_time = records[-1][1] if records else None
    mock_reader.message_count = len(records)
    mock_reader.topics = {conn.topic: conn for conn in connections}
    mock_reader.connections = connections

    def _messages(connections=None, start=None, stop=None):
        conns_to_use = connections or mock_reader.connections
        topic_set = {conn.topic for conn in conns_to_use}
        for topic, timestamp, raw in records:
            if topic not in topic_set:
                continue
            if start is not None and timestamp < start:
                continue
            if stop is not None and timestamp >= stop:
                continue
            yield conn_by_topic[topic], timestamp, raw

    def _deserialize(rawdata, msgtype):
        return payload_by_raw[rawdata]

    mock_reader.messages = MagicMock(side_effect=_messages)
    mock_reader.deserialize = _deserialize
    return mock_reader


def test_assemble_trigger_records_supports_last_known_before_and_defaults(tmp_path):
    mock_reader = make_mock_any_reader_with_payloads(
        topics={"/trigger": "custom_msgs/msg/Trigger", "/joy": "sensor_msgs/msg/Joy"},
        messages=[
            ("/trigger", 100, {"frame": {"value": 1}}),
            ("/joy", 80, {"buttons": [1, 2]}),
            ("/trigger", 200, {"frame": {"value": 2}}),
        ],
    )

    with _patch_any_reader(mock_reader):
        from hephaes.reader import ROS1Reader

        bag_path = tmp_path / "test.bag"
        bag_path.write_bytes(b"")
        reader = ROS1Reader(str(bag_path))
        records, dropped = assemble_trigger_records(
            reader=reader,
            trigger_topic="/trigger",
            joins=[
                JoinSpec(
                    topic="/joy",
                    sync_policy="last-known-before",
                    required=True,
                    default_value={"buttons": [0, 0]},
                )
            ],
        )
        reader.close()

    assert dropped == 0
    assert [record.timestamp_ns for record in records] == [100, 200]
    assert records[0].values["/joy"] == {"buttons": [1, 2]}
    assert records[1].values["/joy"] == {"buttons": [1, 2]}
    assert records[0].presence["/joy"] == 1


def test_assemble_trigger_records_supports_exact_within_tolerance(tmp_path):
    mock_reader = make_mock_any_reader_with_payloads(
        topics={"/trigger": "custom_msgs/msg/Trigger", "/joy": "sensor_msgs/msg/Joy"},
        messages=[
            ("/trigger", 100, {"frame": {"value": 1}}),
            ("/joy", 108, {"buttons": [5, 6]}),
        ],
    )

    with _patch_any_reader(mock_reader):
        from hephaes.reader import ROS1Reader

        bag_path = tmp_path / "test.bag"
        bag_path.write_bytes(b"")
        reader = ROS1Reader(str(bag_path))
        records, dropped = assemble_trigger_records(
            reader=reader,
            trigger_topic="/trigger",
            joins=[
                JoinSpec(
                    topic="/joy",
                    sync_policy="exact-within-tolerance",
                    tolerance_ns=10,
                    required=True,
                )
            ],
        )
        reader.close()

    assert dropped == 0
    assert len(records) == 1
    assert records[0].values["/joy"] == {"buttons": [5, 6]}
    assert records[0].presence["/joy"] == 1


def test_converter_spec_path_emits_presence_flags_for_trigger_assembly(tmp_bag_file, tmp_path):
    mock_reader = make_mock_any_reader_with_payloads(
        topics={"/trigger": "custom_msgs/msg/Trigger", "/joy": "sensor_msgs/msg/Joy"},
        messages=[
            ("/trigger", 100, {"frame": {"value": 1}}),
            ("/joy", 150, {"buttons": [3.2, 4.9]}),
            ("/trigger", 200, {"frame": {"value": 2}}),
        ],
    )

    spec = ConversionSpec(
        schema=SchemaSpec(name="trigger_demo", version=1),
        assembly={
            "trigger_topic": "/trigger",
            "joins": [
                {
                    "topic": "/joy",
                    "sync_policy": "last-known-before",
                    "required": True,
                    "default_value": {"buttons": [0, 0]},
                }
            ],
        },
        features={
            "frame": FeatureSpec(
                source=FieldSourceSpec(topic="/trigger", field_path="frame.value"),
                dtype="int64",
                required=True,
            ),
            "buttons": FeatureSpec(
                source=FieldSourceSpec(topic="/joy", field_path="buttons"),
                dtype="int64",
                shape=[2],
                required=True,
                transforms=[{"cast": {"dtype": "int64"}}],
            ),
        },
        output=OutputSpec(format="tfrecord"),
    )

    with _patch_any_reader(mock_reader):
        converter = Converter(
            [str(tmp_bag_file)],
            None,
            tmp_path,
            spec=spec,
            max_workers=1,
            output="tfrecord",
        )
        results = converter.convert()

    rows = list(stream_tfrecord_rows(results[0]))
    assert [row["timestamp_ns"] for row in rows] == [100, 200]
    assert rows[0]["frame__present"] == 1
    assert rows[0]["frame"] == 1
    assert rows[0]["buttons__present"] == 0
    assert rows[1]["frame__present"] == 1
    assert rows[1]["buttons__present"] == 1
    assert rows[1]["buttons"] == [3, 4]


def test_converter_spec_path_shards_trigger_outputs_with_default_layout(tmp_bag_file, tmp_path):
    mock_reader = make_mock_any_reader_with_payloads(
        topics={"/trigger": "custom_msgs/msg/Trigger"},
        messages=[
            ("/trigger", 100, {"frame": {"value": 1}}),
            ("/trigger", 200, {"frame": {"value": 2}}),
            ("/trigger", 300, {"frame": {"value": 3}}),
            ("/trigger", 400, {"frame": {"value": 4}}),
        ],
    )

    spec = ConversionSpec(
        schema=SchemaSpec(name="sharded_trigger_demo", version=1),
        assembly={
            "trigger_topic": "/trigger",
            "joins": [],
        },
        features={
            "frame": FeatureSpec(
                source=FieldSourceSpec(topic="/trigger", field_path="frame.value"),
                dtype="int64",
                required=True,
            ),
        },
        output=OutputSpec(format="tfrecord", shards=2),
    )

    with _patch_any_reader(mock_reader):
        converter = Converter(
            [str(tmp_bag_file)],
            None,
            tmp_path,
            spec=spec,
            max_workers=1,
            output="tfrecord",
        )
        results = converter.convert()

    assert [path.name for path in results] == [
        "episode_0001-00000-of-00002.tfrecord",
        "episode_0001-00001-of-00002.tfrecord",
    ]
    assert [row["timestamp_ns"] for row in stream_tfrecord_rows(results[0])] == [100, 200]
    assert [row["timestamp_ns"] for row in stream_tfrecord_rows(results[1])] == [300, 400]


def test_converter_spec_validation_enforces_bad_record_budget(tmp_bag_file, tmp_path):
    mock_reader = make_mock_any_reader_with_payloads(
        topics={"/trigger": "custom_msgs/msg/Trigger"},
        messages=[
            ("/trigger", 100, {"frame": {"value": [1, 2]}}),
        ],
    )

    spec = ConversionSpec(
        schema=SchemaSpec(name="trigger_validation_demo", version=1),
        assembly={
            "trigger_topic": "/trigger",
            "joins": [],
        },
        features={
            "frame": FeatureSpec(
                source=FieldSourceSpec(topic="/trigger", field_path="frame.value"),
                dtype="int64",
                shape=[3],
                required=True,
                transforms=[
                    {"length": {"exact": 3}},
                    {"cast": {"dtype": "int64"}},
                ],
            ),
        },
        validation={
            "sample_n": 1,
            "fail_fast": False,
            "bad_record_budget": 0,
        },
        output=OutputSpec(format="tfrecord"),
    )

    with _patch_any_reader(mock_reader):
        converter = Converter(
            [str(tmp_bag_file)],
            None,
            tmp_path,
            spec=spec,
            max_workers=1,
            output="tfrecord",
        )

        with pytest.raises(ValueError, match="bad_record_budget"):
            converter.convert()
