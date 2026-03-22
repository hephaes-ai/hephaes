from __future__ import annotations

from hephaes.conversion.capabilities import build_conversion_capabilities


def test_conversion_capabilities_expose_expected_surface():
    capabilities = build_conversion_capabilities()

    assert capabilities.spec_version == 1
    assert "trigger" in capabilities.row_strategies
    assert "per-message" in capabilities.row_strategies
    assert "path" in capabilities.feature_source_kinds
    assert "cast" in capabilities.transform_kinds
    assert "image_encode" in capabilities.transform_kinds
    assert "float64" in capabilities.feature_dtypes
    assert capabilities.supports_spec_documents is True
    assert capabilities.supports_inspection is True
    assert capabilities.supports_draft_generation is True
    assert capabilities.supports_preview is True
    assert capabilities.supports_migration is True
