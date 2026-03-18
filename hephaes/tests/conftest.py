from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


def _make_connection(topic: str, msgtype: str) -> MagicMock:
    conn = MagicMock()
    conn.topic = topic
    conn.msgtype = msgtype
    return conn


def make_mock_any_reader(
    topics: dict[str, str] | None = None,
    messages: list[tuple[str, int, Any]] | None = None,
    start_time: int = 1_000_000_000,
    end_time: int = 2_000_000_000,
    message_count: int | None = None,
) -> MagicMock:
    topics = topics or {"/cmd_vel": "geometry_msgs/Twist"}
    messages = messages or []

    connections = [_make_connection(t, m) for t, m in topics.items()]

    # Build a Connection-keyed lookup so deserialize can return per-message data
    conn_by_topic: dict[str, MagicMock] = {c.topic: c for c in connections}

    mock_reader = MagicMock()
    mock_reader.start_time = start_time
    mock_reader.end_time = end_time
    mock_reader.message_count = message_count if message_count is not None else len(messages)

    # topics property: {topic: Connection}
    mock_reader.topics = {conn.topic: conn for conn in connections}
    mock_reader.connections = connections

    def _messages(connections=None):
        conns_to_use = connections or mock_reader.connections
        topic_set = {c.topic for c in conns_to_use}
        for topic, timestamp, data in messages:
            if topic in topic_set:
                yield conn_by_topic[topic], timestamp, b"rawdata"

    mock_reader.messages = _messages

    def _deserialize(rawdata, msgtype):
        # Return a simple dict so JSON serialization works
        return {"value": 1}

    mock_reader.deserialize = _deserialize

    return mock_reader


@pytest.fixture()
def tmp_bag_file(tmp_path: Path) -> Path:
    bag = tmp_path / "test.bag"
    bag.write_bytes(b"")
    return bag


@pytest.fixture()
def tmp_mcap_file(tmp_path: Path) -> Path:
    mcap = tmp_path / "test.mcap"
    mcap.write_bytes(b"")
    return mcap


@pytest.fixture()
def simple_topics() -> dict[str, str]:
    return {"/cmd_vel": "geometry_msgs/Twist", "/odom": "nav_msgs/Odometry"}


@pytest.fixture()
def simple_messages() -> list[tuple[str, int, Any]]:
    return [
        ("/cmd_vel", 1_000_000_000, {"linear": 1.0}),
        ("/odom", 1_500_000_000, {"pose": {}}),
        ("/cmd_vel", 2_000_000_000, {"linear": 2.0}),
    ]
