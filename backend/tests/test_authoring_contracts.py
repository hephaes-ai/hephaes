from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import inspect as sa_inspect

from app.schemas.conversion_authoring import (
    ConversionAuthoringCapabilitiesResponse,
    ConversionDraftRequest,
    ConversionDraftResponse,
    ConversionInspectionRequest,
    ConversionInspectionResponse,
    ConversionPreviewRequest,
    ConversionPreviewResponse,
    SavedConversionConfigCreateRequest,
    SavedConversionConfigDetailResponse,
    SavedConversionConfigRevisionResponse,
    SavedConversionDraftRevisionResponse,
)
from hephaes import build_doom_ros_train_py_compatible
from hephaes.conversion.draft_spec import DraftSpecRequest, DraftSpecResult
from hephaes.conversion.introspection import InspectionResult
from hephaes.conversion.preview import PreviewResult, PreviewRow
from hephaes.conversion.spec_io import build_conversion_spec_document


def test_authoring_capabilities_expose_backend_persistence_surface():
    capabilities = ConversionAuthoringCapabilitiesResponse()

    assert capabilities.authoring_api_version == 1
    assert capabilities.persistence.mode == "sqlite-json"
    assert capabilities.persistence.supports_saved_configs is True
    assert capabilities.persistence.supports_draft_revisions is True
    assert capabilities.persistence.supports_execute_from_saved_config is True
    assert capabilities.persistence.spec_document_version == 2
    assert capabilities.hephaes.supports_preview is True
    assert capabilities.hephaes.supports_migration is True
    assert capabilities.hephaes.row_strategies == ["trigger", "per-message", "resample"]
    assert capabilities.output_contract.policy_version == 1
    assert capabilities.output_contract.default_image_payload_contract == "bytes_v2"
    assert capabilities.output_contract.supported_image_payload_contracts == ["bytes_v2", "legacy_list_v1"]


def test_authoring_requests_and_responses_normalize_and_serialize():
    spec = build_doom_ros_train_py_compatible()
    document = build_conversion_spec_document(spec, metadata={"owner": "qa"})

    saved_config = SavedConversionConfigCreateRequest(
        name="  Demo Config  ",
        description="  A reusable config for tests  ",
        metadata={"owner": "qa"},
        spec=spec,
    )
    inspection_request = ConversionInspectionRequest(
        asset_id="  asset-123  ",
        topics=[" /camera/front/image_raw ", "/joy", "/camera/front/image_raw"],
        sample_n=4,
    )
    draft_request = ConversionDraftRequest(
        asset_id="  asset-123  ",
        topics=[" /camera/front/image_raw ", "/joy", "/camera/front/image_raw"],
        sample_n=4,
        draft_request=DraftSpecRequest(include_preview=False, preview_rows=3),
    )
    preview_request = ConversionPreviewRequest(asset_id="  asset-123  ", spec=spec, sample_n=2)

    inspection = InspectionResult(bag_path="/tmp/demo.mcap", sample_n=4, topics={})
    draft_result = DraftSpecResult(
        request=DraftSpecRequest(include_preview=False),
        spec=spec,
        selected_topics=["/camera/front/image_raw"],
        trigger_topic="/camera/front/image_raw",
        join_topics=["/joy"],
        warnings=["preview skipped"],
        assumptions=["assumed trigger topic"],
        unresolved_fields=[],
        preview=None,
    )
    preview = PreviewResult(
        rows=[
            PreviewRow(
                timestamp_ns=1,
                field_data={"image": b"\x00\x01"},
                presence_data={"image": 1},
            )
        ],
        checked_records=1,
        bad_records=0,
    )

    inspection_response = ConversionInspectionResponse(
        asset_id="asset-123",
        request=inspection_request,
        inspection=inspection,
        representation_policy={
            "output_format": "tfrecord",
            "image_payload_contract": "bytes_v2",
        },
    )
    draft_response = ConversionDraftResponse(
        asset_id="asset-123",
        request=draft_request,
        inspection=inspection,
        draft=draft_result,
        draft_revision_id=None,
        representation_policy={
            "output_format": "tfrecord",
            "image_payload_contract": "bytes_v2",
        },
    )
    preview_response = ConversionPreviewResponse(
        asset_id="asset-123",
        request=preview_request,
        preview=preview,
        representation_policy={
            "output_format": "tfrecord",
            "image_payload_contract": "bytes_v2",
        },
    )
    revision_response = SavedConversionConfigRevisionResponse(
        id="revision-1",
        config_id="config-1",
        revision_number=1,
        change_kind="create",
        change_summary="initial save",
        spec_document_version=document.spec_version,
        spec_document_json=document.model_dump(mode="json", by_alias=True),
        resolved_spec=spec,
        created_at=datetime(2026, 3, 22, tzinfo=UTC),
    )
    draft_revision_response = SavedConversionDraftRevisionResponse(
        id="draft-1",
        saved_config_id="config-1",
        revision_number=1,
        source_asset_id="asset-123",
        status="draft",
        inspection_request=inspection_request,
        inspection=inspection,
        draft_request=draft_request.draft_request,
        draft_result=draft_result,
        preview=preview,
        created_at=datetime(2026, 3, 22, tzinfo=UTC),
        updated_at=datetime(2026, 3, 22, tzinfo=UTC),
    )
    detail_response = SavedConversionConfigDetailResponse(
        id="config-1",
        name="Demo Config",
        description="A reusable config for tests",
        metadata={"owner": "qa"},
        spec_document_version=document.spec_version,
        spec_schema_name=spec.schema.name,
        spec_schema_version=spec.schema.version,
        spec_row_strategy_kind=spec.row_strategy.kind if spec.row_strategy is not None else None,
        spec_output_format=spec.output.format,
        spec_output_compression=spec.output.compression,
        spec_feature_count=len(spec.features),
        revision_count=1,
        draft_count=1,
        migration_notes=["stored as the current document version"],
        invalid_reason=None,
        latest_preview_available=True,
        latest_preview_updated_at=datetime(2026, 3, 22, tzinfo=UTC),
        created_at=datetime(2026, 3, 22, tzinfo=UTC),
        updated_at=datetime(2026, 3, 22, tzinfo=UTC),
        last_opened_at=None,
        status="ready",
        spec_document_json=document.model_dump(mode="json", by_alias=True),
        resolved_spec=spec,
        resolved_spec_document=document,
        latest_preview=preview,
        revisions=[revision_response],
        draft_revisions=[draft_revision_response],
    )

    assert saved_config.name == "Demo Config"
    assert saved_config.description == "A reusable config for tests"
    assert inspection_request.asset_id == "asset-123"
    assert inspection_request.topics == ["/camera/front/image_raw", "/joy"]
    assert draft_request.asset_id == "asset-123"
    assert draft_request.topics == ["/camera/front/image_raw", "/joy"]
    assert preview_request.asset_id == "asset-123"
    assert preview_response.preview.rows[0].field_data["image"] == b"\x00\x01"
    assert detail_response.resolved_spec == spec
    assert detail_response.resolved_spec_document == document
    assert draft_revision_response.preview == preview
    assert draft_response.draft == draft_result

    # Phase 1 depends on these shapes being JSON-safe when persisted.
    assert detail_response.model_dump(mode="json")["revisions"][0]["spec_document_json"]["spec"]["schema"][
        "name"
    ] == spec.schema.name
    assert draft_revision_response.model_dump(mode="json")["preview"]["rows"][0]["timestamp_ns"] == 1


def test_backend_database_only_keeps_runtime_tables(client):
    table_names = set(sa_inspect(client.app.state.engine).get_table_names())

    assert "jobs" in table_names
    assert "output_actions" in table_names
    assert "conversion_configs" not in table_names
    assert "conversion_config_revisions" not in table_names
    assert "conversion_draft_revisions" not in table_names
