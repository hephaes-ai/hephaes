from __future__ import annotations

from hephaes import build_doom_ros_train_py_compatible
from hephaes.conversion.spec_io import (
    ConversionSpecDocument,
    build_conversion_spec_document,
    dump_conversion_spec,
    dump_conversion_spec_document,
    load_conversion_spec,
    load_conversion_spec_document,
    migrate_conversion_spec_document,
    migrate_conversion_spec_payload,
    set_tfrecord_image_payload_contract,
)


def test_conversion_spec_json_round_trip():
    spec = build_doom_ros_train_py_compatible()

    encoded = dump_conversion_spec(spec)
    decoded = load_conversion_spec(encoded)

    assert decoded == spec


def test_conversion_spec_document_round_trip_json_and_yaml():
    spec = build_doom_ros_train_py_compatible()
    document = build_conversion_spec_document(
        spec,
        metadata={"name": "doom", "tags": ["demo"]},
    )

    json_text = dump_conversion_spec_document(document)
    yaml_text = dump_conversion_spec_document(document, format="yaml")

    loaded_from_json = load_conversion_spec_document(json_text)
    loaded_from_yaml = load_conversion_spec_document(yaml_text)

    assert loaded_from_json == document
    assert loaded_from_yaml == document


def test_conversion_spec_document_loads_raw_spec_payload():
    spec = build_doom_ros_train_py_compatible()
    payload = spec.model_dump(by_alias=True)

    document = load_conversion_spec_document(payload)

    assert isinstance(document, ConversionSpecDocument)
    assert document.spec == spec
    assert document.spec_version == 2


def test_conversion_spec_payload_migration_normalizes_schema_aliases():
    payload = {
        "schema_name": "example",
        "schema_version": 3,
        "input": {},
        "decoding": {},
        "output": {"format": "tfrecord"},
    }

    migrated = migrate_conversion_spec_payload(payload)

    assert migrated["schema"] == {"name": "example", "version": 3}
    assert "schema_name" not in migrated
    assert "schema_version" not in migrated


def test_conversion_spec_payload_migration_adds_row_strategy_and_source_kinds():
    payload = {
        "schema": {"name": "example", "version": 1},
        "assembly": {"trigger_topic": "/camera", "joins": [{"topic": "/joy"}]},
        "features": {
            "image": {"source": {"topic": "/camera", "field_path": "data"}, "dtype": "bytes"}
        },
        "output": {"format": "tfrecord"},
    }

    migrated = migrate_conversion_spec_payload(payload, source_version=1)

    assert migrated["row_strategy"]["kind"] == "trigger"
    assert migrated["row_strategy"]["trigger_topic"] == "/camera"
    assert migrated["features"]["image"]["source"]["kind"] == "path"
    assert migrated["output"]["image_payload_contract"] == "legacy_list_v1"


def test_set_tfrecord_image_payload_contract_updates_spec_output_mode():
    spec = build_doom_ros_train_py_compatible()

    updated = set_tfrecord_image_payload_contract(
        spec,
        contract="legacy_list_v1",
    )

    assert updated.output.format == "tfrecord"
    assert updated.output.image_payload_contract == "legacy_list_v1"
    assert spec.output.image_payload_contract == "bytes_v2"


def test_conversion_spec_document_migration_noops_on_current_version():
    document = build_conversion_spec_document(build_doom_ros_train_py_compatible())

    migrated = migrate_conversion_spec_document(document)

    assert migrated == document
