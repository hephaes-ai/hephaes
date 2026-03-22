"""Tests for the conversion discovery and feature-path helpers."""

from __future__ import annotations

from hephaes.conversion import discover_input_paths, filter_topics, resolve_field_path


def test_discover_input_paths_expands_directories_and_recursion(tmp_path):
    top_mcap = tmp_path / "a.mcap"
    top_bag = tmp_path / "b.bag"
    ignored = tmp_path / "ignore.txt"
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    nested_mcap = nested_dir / "c.mcap"

    top_mcap.write_bytes(b"")
    top_bag.write_bytes(b"")
    ignored.write_bytes(b"")
    nested_mcap.write_bytes(b"")

    shallow = discover_input_paths([tmp_path])
    deep = discover_input_paths([tmp_path], recursive=True)

    assert shallow == [top_mcap.resolve(), top_bag.resolve()]
    assert deep == [top_mcap.resolve(), top_bag.resolve(), nested_mcap.resolve()]


def test_discover_input_paths_supports_globs(tmp_path):
    first = tmp_path / "episode_01.mcap"
    second = tmp_path / "episode_02.mcap"
    first.write_bytes(b"")
    second.write_bytes(b"")

    result = discover_input_paths([str(tmp_path / "episode_*.mcap")])

    assert result == [first.resolve(), second.resolve()]


def test_filter_topics_applies_include_and_exclude_patterns():
    topics = {
        "/camera/image": "sensor_msgs/msg/Image",
        "/joy": "sensor_msgs/msg/Joy",
        "/tf": "tf2_msgs/msg/TFMessage",
    }

    filtered = filter_topics(
        topics,
        include_topics=["/camera/*", "/joy"],
        exclude_topics=["/tf"],
    )

    assert filtered == {
        "/camera/image": "sensor_msgs/msg/Image",
        "/joy": "sensor_msgs/msg/Joy",
    }


def test_resolve_field_path_handles_nested_dicts_and_lists():
    payload = {
        "pose": {
            "position": [10, 20, 30],
            "label": "robot",
        }
    }

    assert resolve_field_path(payload, None) == payload
    assert resolve_field_path(payload, "pose.label") == "robot"
    assert resolve_field_path(payload, "pose.position.1") == 20
