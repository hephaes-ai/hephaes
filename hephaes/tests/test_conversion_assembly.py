"""Tests for the conversion assembly stage."""

from __future__ import annotations

from hephaes.conversion import build_mapping_resolution, resolve_mapping_for_bag
from hephaes.models import MappingTemplate


def test_resolve_mapping_for_bag_prefers_first_available_topic():
    mapping = MappingTemplate.model_validate(
        {
            "cmd_vel": ["/missing", "/cmd_vel"],
            "odom": ["/odom"],
        }
    )

    plan = resolve_mapping_for_bag(
        mapping=mapping,
        available_topics={"/cmd_vel": "geometry_msgs/Twist", "/odom": "nav_msgs/Odometry"},
    )

    assert plan.topics_to_read == ["/cmd_vel", "/odom"]
    assert plan.topic_to_field == {"/cmd_vel": "cmd_vel", "/odom": "odom"}


def test_build_mapping_resolution_tracks_missing_fields():
    mapping_resolution = build_mapping_resolution(
        field_names=["cmd_vel", "odom"],
        topic_to_field={"/cmd_vel": "cmd_vel"},
    )

    assert mapping_resolution == {"cmd_vel": "/cmd_vel", "odom": None}
