"""Tests for feature extraction and transform application."""

from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image

from hephaes.conversion import FeatureBuilder, FeatureEvaluationContext
from hephaes.models import FeatureSpec, FieldSourceSpec, MetadataSourceSpec


def test_feature_builder_applies_cast_and_length_transforms():
    feature = FeatureSpec(
        source=FieldSourceSpec(topic="/joy", field_path="buttons"),
        dtype="int64",
        shape=[3],
        transforms=[
            {"length": {"exact": 3}},
            {"cast": {"dtype": "int64"}},
        ],
    )

    value = FeatureBuilder().build({"buttons": [1.2, 2.0, 3.8]}, feature)

    assert value == [1, 2, 3]


def test_feature_builder_applies_image_color_convert_and_encode():
    feature = FeatureSpec(
        source=FieldSourceSpec(topic="/camera"),
        dtype="bytes",
        transforms=[
            {"image_color_convert": {"from": "bgra", "to": "rgb"}},
            {"image_encode": {"format": "png"}},
        ],
    )

    encoded = FeatureBuilder().build(
        np.array([[[0, 128, 255, 255]]], dtype=np.uint8),
        feature,
    )

    with Image.open(BytesIO(encoded)) as image:
        assert image.mode == "RGB"
        assert image.size == (1, 1)
        assert image.getpixel((0, 0)) == (255, 128, 0)


def test_feature_builder_rejects_length_mismatch():
    feature = FeatureSpec(
        source=FieldSourceSpec(topic="/joy", field_path="buttons"),
        dtype="int64",
        shape=[3],
        transforms=[{"length": {"exact": 3}}],
    )

    try:
        FeatureBuilder().build({"buttons": [1, 2]}, feature)
    except ValueError as exc:
        assert "expected sequence length 3" in str(exc)
    else:  # pragma: no cover - the assertion above should always fail first
        raise AssertionError("expected a length validation error")


def test_feature_builder_supports_constant_metadata_concat_and_stack_sources():
    context = FeatureEvaluationContext.from_row(
        timestamp_ns=123,
        values={"/joy": {"buttons": [1, 2], "axes": [0.25, -0.25]}},
        presence={"/joy": 1},
    )
    builder = FeatureBuilder()

    constant_feature = FeatureSpec(
        source={"kind": "constant", "value": [9]},
        dtype="json",
    )
    metadata_feature = FeatureSpec(
        source=MetadataSourceSpec(key="timestamp_ns"),
        dtype="int64",
    )
    concat_feature = FeatureSpec(
        source={
            "kind": "concat",
            "sources": [
                {"topic": "/joy", "field_path": "buttons"},
                {"kind": "constant", "value": [9]},
            ],
        },
        dtype="json",
    )
    stack_feature = FeatureSpec(
        source={
            "kind": "stack",
            "sources": [
                {"topic": "/joy", "field_path": "axes"},
                {"kind": "constant", "value": [0.0, 0.0]},
            ],
        },
        dtype="json",
    )

    assert builder.build(context, constant_feature) == [9]
    assert builder.build(context, metadata_feature) == 123
    assert builder.build(context, concat_feature) == [1, 2, 9]
    assert builder.build(context, stack_feature) == [[0.25, -0.25], [0.0, 0.0]]


def test_feature_builder_rejects_invalid_concat_of_scalars():
    context = FeatureEvaluationContext.from_row(
        timestamp_ns=123,
        values={"/joy": {"button": 1}},
        presence={"/joy": 1},
    )
    feature = FeatureSpec(
        source={
            "kind": "concat",
            "sources": [
                {"topic": "/joy", "field_path": "button"},
                {"kind": "constant", "value": 2},
            ],
        },
        dtype="json",
    )

    try:
        FeatureBuilder().build(context, feature)
    except ValueError as exc:
        assert "concat requires sequence or array values" in str(exc)
    else:  # pragma: no cover - the assertion above should always fail first
        raise AssertionError("expected a concat validation error")


def test_feature_builder_rejects_missing_metadata_without_default():
    context = FeatureEvaluationContext.from_row(
        timestamp_ns=123,
        values={},
        presence={},
    )
    feature = FeatureSpec(
        source={"kind": "metadata", "key": "episode_id"},
        dtype="json",
    )

    try:
        FeatureBuilder().build(context, feature)
    except KeyError as exc:
        assert "missing metadata key" in str(exc)
    else:  # pragma: no cover - the assertion above should always fail first
        raise AssertionError("expected a missing metadata error")
