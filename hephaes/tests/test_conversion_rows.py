from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hephaes import Converter
from hephaes.conversion import construct_rows
from hephaes.conversion.preview import preview_conversion_spec
from hephaes.models import ConversionSpec, FeatureSpec, FieldSourceSpec, Message, OutputSpec, SchemaSpec
from hephaes.tfrecord import stream_tfrecord_rows


class FakeRowReader:
    def __init__(
        self,
        *,
        topics: dict[str, str],
        messages: list[tuple[str, int, object]],
        bag_path: str = "/tmp/test.mcap",
        ros_version: str = "ROS2",
    ) -> None:
        self.topics = topics
        self._messages = messages
        self.bag_path = Path(bag_path)
        self.ros_version = ros_version

    def read_messages(self, topics=None, on_failure="warn", topic_type_hints=None):
        topic_filter = set(topics) if topics else None
        for topic, timestamp, payload in self._messages:
            if topic_filter is not None and topic not in topic_filter:
                continue
            yield Message(timestamp=timestamp, topic=topic, data=payload)


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


def test_construct_rows_supports_per_message_strategy():
    reader = FakeRowReader(
        topics={"/joy": "sensor_msgs/msg/Joy"},
        messages=[
            ("/joy", 100, {"buttons": [1, 0, 0]}),
            ("/joy", 200, {"buttons": [0, 1, 0]}),
        ],
    )
    spec = ConversionSpec(
        schema=SchemaSpec(name="per_message_demo", version=1),
        row_strategy={"kind": "per-message", "topic": "/joy"},
        features={
            "buttons": FeatureSpec(
                source=FieldSourceSpec(topic="/joy", field_path="buttons"),
                dtype="int64",
            )
        },
        output=OutputSpec(format="tfrecord"),
    )

    row_result = construct_rows(reader=reader, spec=spec)

    assert row_result.dropped_count == 0
    assert [record.timestamp_ns for record in row_result.records] == [100, 200]
    assert row_result.records[0].values["/joy"]["buttons"] == [1, 0, 0]
    assert row_result.records[1].presence["/joy"] == 1


def test_preview_supports_resample_interpolate_strategy():
    reader = FakeRowReader(
        topics={"/joy": "sensor_msgs/msg/Joy"},
        messages=[
            ("/joy", 1_000_000_000, {"axis": 0.0}),
            ("/joy", 2_000_000_000, {"axis": 1.0}),
        ],
    )
    spec = ConversionSpec(
        schema=SchemaSpec(name="resample_demo", version=1),
        row_strategy={"kind": "resample", "freq_hz": 2.0, "method": "interpolate"},
        features={
            "axis": FeatureSpec(
                source=FieldSourceSpec(topic="/joy", field_path="axis"),
                dtype="float64",
            )
        },
        output=OutputSpec(format="tfrecord"),
    )

    preview = preview_conversion_spec(reader, spec, sample_n=3)

    assert preview.dropped_count == 0
    assert [row.timestamp_ns for row in preview.rows] == [
        1_000_000_000,
        1_500_000_000,
        2_000_000_000,
    ]
    assert preview.rows[1].presence_data["axis"] == 1
    assert preview.rows[1].field_data["axis"] == pytest.approx(0.5)


def test_converter_supports_per_message_row_strategy(tmp_bag_file, tmp_path):
    mock_reader = make_mock_any_reader_with_payloads(
        topics={"/joy": "sensor_msgs/msg/Joy"},
        messages=[
            ("/joy", 100, {"buttons": [1, 0, 0]}),
            ("/joy", 200, {"buttons": [0, 1, 0]}),
        ],
    )
    spec = ConversionSpec(
        schema=SchemaSpec(name="per_message_converter_demo", version=1),
        row_strategy={"kind": "per-message", "topic": "/joy"},
        features={
            "buttons": FeatureSpec(
                source=FieldSourceSpec(topic="/joy", field_path="buttons"),
                dtype="int64",
                shape=[3],
            )
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
    assert rows[0]["buttons__present"] == 1
    assert rows[0]["buttons"] == [1, 0, 0]
    assert rows[1]["buttons"] == [0, 1, 0]
