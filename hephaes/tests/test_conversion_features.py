"""Tests for feature extraction and transform application."""

from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image

from hephaes.conversion import FeatureBuilder
from hephaes.models import FeatureSpec, FieldSourceSpec


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
