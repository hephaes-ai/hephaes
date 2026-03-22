"""Tests for the conversion decoding stage."""

from __future__ import annotations

from unittest.mock import MagicMock

from hephaes.conversion import MessageDecoder, build_message_decoder
from hephaes.models import DecodingSpec, Message


def test_build_message_decoder_uses_topic_hints_and_failure_policy():
    decoding = DecodingSpec.model_validate(
        {
            "topics": {
                "/camera": {"type_hint": "custom_msgs/msg/Image"},
                "/joy": {"type_hint": "sensor_msgs/msg/Joy"},
            },
            "on_decode_failure": "fail",
        }
    )

    decoder = build_message_decoder(decoding)

    assert decoder.on_failure == "fail"
    assert decoder.topic_type_hints == {
        "/camera": "custom_msgs/msg/Image",
        "/joy": "sensor_msgs/msg/Joy",
    }


def test_message_decoder_delegates_to_reader_with_policies():
    reader = MagicMock()
    reader.read_messages.return_value = iter(
        [Message(timestamp=1, topic="/camera", data={"frame": 1})]
    )

    decoder = MessageDecoder(
        topic_type_hints={"/camera": "custom_msgs/msg/Image"},
        on_failure="warn",
    )

    result = list(decoder.iter_messages(reader, topics=["/camera"], start_ns=10, stop_ns=20))

    assert result == [Message(timestamp=1, topic="/camera", data={"frame": 1})]
    reader.read_messages.assert_called_once_with(
        topics=["/camera"],
        start_ns=10,
        stop_ns=20,
        on_failure="warn",
        topic_type_hints={"/camera": "custom_msgs/msg/Image"},
    )
