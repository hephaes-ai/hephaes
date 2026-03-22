from __future__ import annotations

from pathlib import Path

from hephaes import build_doom_ros_train_py_compatible
from hephaes.conversion.draft_spec import DraftSpecRequest, build_draft_conversion_spec
from hephaes.conversion.introspection import inspect_reader
from hephaes.conversion.preview import preview_conversion_spec
from hephaes.models import Message


class FakeAuthoringReader:
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


def _build_authoring_reader() -> FakeAuthoringReader:
    buttons_a = [1, 0, 0] + [0] * 12
    buttons_b = [0, 1, 0] + [0] * 12
    return FakeAuthoringReader(
        topics={
            "/doom_image": "custom_msgs/msg/RawImageBGRA",
            "/joy": "sensor_msgs/msg/Joy",
        },
        messages=[
            ("/joy", 90, {"buttons": buttons_a, "axes": [0.0, 0.5]}),
            ("/doom_image", 100, {"data": bytes(range(16))}),
            ("/joy", 190, {"buttons": buttons_b, "axes": [0.25, -0.25]}),
            ("/doom_image", 200, {"data": bytes(range(16, 32))}),
        ],
    )


def test_inspection_discovers_bytes_and_sequence_candidates():
    reader = _build_authoring_reader()

    inspection = inspect_reader(reader, sample_n=2)

    doom_topic = inspection.topics["/doom_image"]
    joy_topic = inspection.topics["/joy"]

    assert doom_topic.message_type == "custom_msgs/msg/RawImageBGRA"
    assert doom_topic.sampled_message_count == 2
    assert doom_topic.sample_timestamps == [100, 200]
    assert doom_topic.field_candidates["data"].kind == "image"
    assert doom_topic.field_candidates["data"].candidate_dtypes == ["bytes"]
    assert doom_topic.field_candidates["data"].image_like is True

    assert joy_topic.sample_timestamps == [90, 190]
    assert joy_topic.field_candidates["buttons"].kind == "sequence"
    assert joy_topic.field_candidates["buttons"].shape_hint == [15]
    assert joy_topic.field_candidates["buttons"].candidate_dtypes == ["int64"]
    assert joy_topic.field_candidates["axes"].candidate_dtypes == ["float32", "float64"]


def test_preview_conversion_spec_uses_trigger_and_join_data():
    reader = _build_authoring_reader()
    spec = build_doom_ros_train_py_compatible()

    preview = preview_conversion_spec(reader, spec, sample_n=2)

    assert preview.dropped_count == 0
    assert preview.warnings == []
    assert len(preview.rows) == 2
    assert preview.rows[0].timestamp_ns == 100
    assert preview.rows[0].presence_data["image"] == 1
    assert preview.rows[0].presence_data["buttons"] == 1
    assert isinstance(preview.rows[0].field_data["image"], (bytes, bytearray))
    assert preview.rows[0].field_data["buttons"][:3] == [1, 0, 0]
    assert len(preview.rows[0].field_data["buttons"]) == 15
    assert preview.rows[1].timestamp_ns == 200
    assert preview.rows[1].field_data["buttons"][:3] == [0, 1, 0]
    assert len(preview.rows[1].field_data["buttons"]) == 15


def test_draft_generation_can_return_preview_and_label_metadata():
    reader = _build_authoring_reader()
    inspection = inspect_reader(reader, sample_n=2)

    request = DraftSpecRequest(
        trigger_topic="/doom_image",
        selected_topics=["/doom_image", "/joy"],
        max_features_per_topic=1,
        label_feature="buttons",
        include_preview=True,
        preview_rows=2,
    )

    draft = build_draft_conversion_spec(inspection, request=request, reader=reader)

    assert draft.trigger_topic == "/doom_image"
    assert draft.join_topics == ["/joy"]
    assert draft.spec.assembly is not None
    assert draft.spec.row_strategy is not None
    assert set(draft.spec.features) == {"image", "buttons"}
    assert draft.spec.input.include_topics == ["/doom_image", "/joy"]
    assert draft.spec.labels is not None
    assert draft.spec.labels.primary == "buttons"
    assert draft.spec.labels.source is not None
    assert draft.spec.labels.source.topic == "/joy"
    assert draft.spec.draft_origin is not None
    assert draft.spec.draft_origin.kind == "inspection"
    assert draft.spec.draft_origin.source_topics == ["/doom_image", "/joy"]
    assert draft.spec.draft_origin.provenance["trigger_topic"] == "/doom_image"
    assert draft.preview_ready is True
    assert draft.preview is not None
    assert len(draft.preview.rows) == 2
    assert draft.preview.rows[0].field_data["image"] is not None
    assert draft.preview.rows[0].field_data["buttons"][:3] == [1, 0, 0]
    assert len(draft.preview.rows[0].field_data["buttons"]) == 15
