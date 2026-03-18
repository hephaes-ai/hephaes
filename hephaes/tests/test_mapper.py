"""Tests for hephaes.mappers."""
import json

import pytest

from hephaes.mappers import build_mapping_template, build_mapping_template_from_json
from hephaes.models import MappingTemplate, Topic


def _topic(name: str) -> Topic:
    return Topic(
        name=name,
        message_type="std_msgs/String",
        message_count=1,
        rate_hz=1.0,
    )


# ---------------------------------------------------------------------------
# build_mapping_template
# ---------------------------------------------------------------------------

class TestBuildMappingTemplate:
    def test_single_topic(self):
        mt = build_mapping_template([_topic("/cmd_vel")])
        assert isinstance(mt, MappingTemplate)
        assert "/cmd_vel" in list(mt.root.values())[0]

    def test_multiple_topics_sorted(self):
        mt = build_mapping_template([_topic("/odom"), _topic("/cmd_vel")])
        keys = list(mt.root.keys())
        # Keys should correspond to sorted topics
        assert len(keys) == 2

    def test_deduplicates_repeated_topics(self):
        mt = build_mapping_template([_topic("/cmd_vel"), _topic("/cmd_vel")])
        # /cmd_vel should appear only once
        all_sources = [t for sources in mt.root.values() for t in sources]
        assert all_sources.count("/cmd_vel") == 1

    def test_empty_topics_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            build_mapping_template([])

    def test_empty_topic_name_raises(self):
        topic = Topic.model_construct(
            name="",
            message_type="std_msgs/String",
            message_count=1,
            rate_hz=1.0,
        )
        with pytest.raises(ValueError, match="non-empty"):
            build_mapping_template([topic])

    def test_non_topic_entry_raises(self):
        with pytest.raises(TypeError, match="Topic objects"):
            build_mapping_template(["/cmd_vel"])  # type: ignore[list-item]

    def test_field_name_strips_leading_slash(self):
        mt = build_mapping_template([_topic("/cmd_vel")])
        assert "cmd_vel" in mt.root

    def test_field_name_replaces_special_chars(self):
        mt = build_mapping_template([_topic("/my/nested/topic")])
        keys = list(mt.root.keys())
        assert len(keys) == 1
        assert "/" not in keys[0]

    def test_duplicate_field_names_resolved(self):
        # Two topics that would normally produce the same field name
        mt = build_mapping_template([_topic("/a/b"), _topic("/a-b")])
        keys = list(mt.root.keys())
        assert len(keys) == len(set(keys)), "Field names must be unique"

    def test_multiple_topics(self):
        mt = build_mapping_template([_topic("/cmd_vel"), _topic("/odom"), _topic("/imu")])
        all_sources = {t for sources in mt.root.values() for t in sources}
        assert all_sources == {"/cmd_vel", "/odom", "/imu"}


# ---------------------------------------------------------------------------
# build_mapping_template_from_json
# ---------------------------------------------------------------------------

class TestBuildMappingTemplateFromJson:
    def test_valid_json_string(self):
        mapping_json = json.dumps({"cmd_vel": ["/cmd_vel"]})
        mt = build_mapping_template_from_json([_topic("/cmd_vel")], mapping_json)
        assert mt.root == {"cmd_vel": ["/cmd_vel"]}

    def test_valid_dict_input(self):
        mt = build_mapping_template_from_json([_topic("/cmd_vel")], {"cmd_vel": ["/cmd_vel"]})
        assert mt.root["cmd_vel"] == ["/cmd_vel"]

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="valid JSON"):
            build_mapping_template_from_json([_topic("/cmd_vel")], "{bad json")

    def test_unknown_topic_strict_raises(self):
        with pytest.raises(ValueError, match="unknown topics"):
            build_mapping_template_from_json(
                [_topic("/cmd_vel")],
                {"cmd_vel": ["/nonexistent"]},
                strict_unknown_topics=True,
            )

    def test_unknown_topic_non_strict_allowed(self):
        mt = build_mapping_template_from_json(
            [_topic("/cmd_vel")],
            {"cmd_vel": ["/nonexistent"]},
            strict_unknown_topics=False,
        )
        assert mt.root["cmd_vel"] == ["/nonexistent"]

    def test_missing_topic_require_all_raises(self):
        with pytest.raises(ValueError, match="missing topics"):
            build_mapping_template_from_json(
                [_topic("/cmd_vel"), _topic("/odom")],
                {"cmd_vel": ["/cmd_vel"]},
                strict_unknown_topics=False,
                require_all_topics=True,
            )

    def test_missing_topic_not_required_allowed(self):
        mt = build_mapping_template_from_json(
            [_topic("/cmd_vel"), _topic("/odom")],
            {"cmd_vel": ["/cmd_vel"]},
            strict_unknown_topics=False,
            require_all_topics=False,
        )
        assert "cmd_vel" in mt.root

    def test_duplicate_topics_across_targets_raises(self):
        with pytest.raises(ValueError, match="duplicate topics"):
            build_mapping_template_from_json(
                [_topic("/cmd_vel")],
                {"field_a": ["/cmd_vel"], "field_b": ["/cmd_vel"]},
                strict_unknown_topics=True,
            )

    def test_multiple_source_topics_per_field(self):
        mt = build_mapping_template_from_json(
            [_topic("/cmd_vel"), _topic("/vel")],
            {"velocity": ["/cmd_vel", "/vel"]},
        )
        assert mt.root["velocity"] == ["/cmd_vel", "/vel"]

    def test_empty_topics_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            build_mapping_template_from_json([], {"cmd_vel": ["/cmd_vel"]})
