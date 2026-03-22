from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generator

from ..models import DecodeFailurePolicy, DecodingSpec, Message
from ..reader import RosReader


@dataclass(frozen=True)
class MessageDecoder:
    topic_type_hints: dict[str, str] = field(default_factory=dict)
    on_failure: DecodeFailurePolicy = "warn"

    def iter_messages(
        self,
        reader: RosReader,
        *,
        topics: list[str] | None = None,
        start_ns: int | None = None,
        stop_ns: int | None = None,
    ) -> Generator[Message, None, None]:
        yield from reader.read_messages(
            topics=topics,
            start_ns=start_ns,
            stop_ns=stop_ns,
            on_failure=self.on_failure,
            topic_type_hints=self.topic_type_hints or None,
        )


def build_message_decoder(decoding: DecodingSpec | None = None) -> MessageDecoder:
    if decoding is None:
        return MessageDecoder()

    topic_type_hints = {
        topic: topic_spec.type_hint
        for topic, topic_spec in decoding.topics.items()
        if topic_spec.type_hint is not None
    }
    return MessageDecoder(
        topic_type_hints=topic_type_hints,
        on_failure=decoding.on_decode_failure,
    )
