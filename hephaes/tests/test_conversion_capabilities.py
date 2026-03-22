from __future__ import annotations

from hephaes.conversion.capabilities import build_conversion_capabilities


def test_conversion_capabilities_expose_expected_surface():
    capabilities = build_conversion_capabilities()
    expected_row_strategies = ["trigger", "per-message", "resample"]
    expected_feature_source_kinds = ["path", "constant", "metadata", "concat", "stack"]

    assert capabilities.spec_version == 2
    assert capabilities.row_strategies == expected_row_strategies
    assert capabilities.authoring_row_strategies == expected_row_strategies
    assert capabilities.planned_row_strategies == []
    assert capabilities.feature_source_kinds == expected_feature_source_kinds
    assert capabilities.authoring_feature_source_kinds == expected_feature_source_kinds
    assert capabilities.planned_feature_source_kinds == []
    assert "cast" in capabilities.transform_kinds
    assert "image_encode" in capabilities.transform_kinds
    assert "float64" in capabilities.feature_dtypes
    assert capabilities.supports_spec_documents is True
    assert capabilities.supports_inspection is True
    assert capabilities.supports_draft_generation is True
    assert capabilities.supports_preview is True
    assert capabilities.supports_migration is True
